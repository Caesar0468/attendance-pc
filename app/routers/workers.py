from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.config import load_config
from app.core.exceptions import BaseAppException
from app.database import get_connection, get_db
from app.face_service import FaceService
from app.repositories.worker_repository import WorkerRepository
from app.schemas import SuccessResponse, WorkerCreateOut, WorkerListOut
from app.services.storage_service import StorageService
from app.services.worker_service import WorkerService
from app.core.auth import get_current_user, require_manager_or_root, require_pairing_or_user
from app.core.deletion_log import log_deletion
from app.schemas.attendance import DeleteReasonRequest

router = APIRouter(prefix="/api/workers", tags=["workers"])

# BUGFIX: every route below except delete_worker used to have NO auth
# dependency whatsoever. On a LAN-bound app (host 0.0.0.0 by default) that
# meant anyone on the same Wi-Fi could list every worker + thumbnail, pull a
# worker's full attendance/wage history, or — worst of all — enroll a new
# "worker" using their own face, or overwrite an existing worker's stored
# face embeddings, with zero authentication. Read-only routes now require
# any logged-in user; routes that change data require manager/root; the one
# route the unauthenticated mobile flow legitimately needs (create_worker)
# now requires either a login OR a short-lived pairing token instead of
# being wide open (see app/core/auth.py:require_pairing_or_user).


@router.get("", response_model=WorkerListOut)
def list_workers(user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        worker_repo = WorkerRepository(conn)
        workers = worker_repo.get_all()
        return {"workers": workers}


@router.post("", response_model=WorkerCreateOut)
async def create_worker(
    name: str = Form(...),
    photos: list[UploadFile] = File(...),
    storage: StorageService = Depends(StorageService),
    face_svc: FaceService = Depends(FaceService.get),
    user: dict = Depends(require_pairing_or_user),
):
    config = load_config()

    try:
        with get_connection() as conn:
            worker_repo = WorkerRepository(conn)
            service = WorkerService(storage, face_svc, worker_repo)
            return await service.enroll_worker(
                name=name,
                photos=photos,
                min_photos=config["photos_per_worker_min"],
                max_photos=config["photos_per_worker_max"],
            )
    except BaseAppException as e:
        raise HTTPException(status_code=getattr(e, "status_code", 400), detail=e.detail) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Could not enroll worker. Please try again.") from e


@router.put("/{worker_id}", response_model=WorkerCreateOut)
async def update_worker(
    worker_id: int,
    name: str | None = Form(default=None),
    photos: list[UploadFile] | None = File(default=None),
    storage: StorageService = Depends(StorageService),
    face_svc: FaceService = Depends(FaceService.get),
    user: dict = Depends(require_manager_or_root),
):
    try:
        with get_connection() as conn:
            worker_repo = WorkerRepository(conn)
            service = WorkerService(storage, face_svc, worker_repo)
            return await service.update_worker(
                worker_id=worker_id,
                name=name,
                photos=photos,
            )
    except BaseAppException as e:
        raise HTTPException(status_code=getattr(e, "status_code", 400), detail=e.detail) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Could not update worker. Please try again.") from e


@router.delete("/{worker_id}", response_model=SuccessResponse)
def delete_worker(
    worker_id: int,
    body: DeleteReasonRequest,
    storage: StorageService = Depends(StorageService),
    face_svc: FaceService = Depends(FaceService.get),
    user: dict = Depends(require_manager_or_root),
    db: sqlite3.Connection = Depends(get_db),
):
    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="A reason is required to delete a worker.")
    worker_row = db.execute("SELECT name FROM workers WHERE id = ?", (worker_id,)).fetchone()
    if not worker_row:
        raise HTTPException(status_code=404, detail="Worker not found")
    log_deletion(
        db, entity_type="worker", entity_id=str(worker_id),
        deleted_by=user["username"], reason=body.reason.strip(),
        extra={"name": worker_row["name"]},
    )
    try:
        with get_connection() as conn:
            worker_repo = WorkerRepository(conn)
            service = WorkerService(storage, face_svc, worker_repo)
            service.delete_worker_and_thumbnail(worker_id)
            return {"success": True}
    except BaseAppException as e:
        raise HTTPException(status_code=getattr(e, "status_code", 400), detail=e.detail) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Could not delete worker.") from e


@router.get("/{worker_id}/profile")
def get_worker_profile(
    worker_id: int,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Returns full attendance history + photo evidence + summary stats for a
    single worker, used to power the Worker Profile modal on the frontend."""
    try:
        worker = db.execute(
            "SELECT id, name, thumbnail_path, created_at FROM workers WHERE id = ?", (worker_id,)
        ).fetchone()
        if not worker:
            raise HTTPException(status_code=404, detail="Worker not found")

        attendance_rows = db.execute(
            """
            SELECT date, morning_present, evening_present, confirmed_by
            FROM attendance
            WHERE worker_id = ?
            ORDER BY date DESC
            LIMIT 180
            """,
            (worker_id,),
        ).fetchall()

        evidence_rows = db.execute(
            """
            SELECT f.date, f.session, f.similarity, p.filename
            FROM attendance_faces f
            JOIN photos_log p ON f.photo_log_id = p.id
            WHERE f.worker_id = ?
            ORDER BY f.date DESC, f.created_at DESC
            LIMIT 40
            """,
            (worker_id,),
        ).fetchall()

        total = len(attendance_rows)
        full_days = sum(1 for r in attendance_rows if r["morning_present"] and r["evening_present"])
        half_days = sum(
            1
            for r in attendance_rows
            if (r["morning_present"] or r["evening_present"])
            and not (r["morning_present"] and r["evening_present"])
        )
        absent_days = total - full_days - half_days

        return {
            "worker": dict(worker),
            "attendance": [dict(r) for r in attendance_rows],
            "evidence": [
                {
                    "date": r["date"],
                    "session": r["session"],
                    "similarity": r["similarity"],
                    "url": f"/photos/{r['date']}/{r['session']}/{r['filename']}",
                }
                for r in evidence_rows
            ],
            "stats": {
                "total_days_recorded": total,
                "full_days": full_days,
                "half_days": half_days,
                "absent_days": absent_days,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        # BUGFIX: previously any unexpected error here (bad row, driver
        # quirk, etc.) fell through to FastAPI's default 500 with a
        # non-JSON body, which the frontend couldn't parse — it always
        # displayed a generic "Could not load worker profile" with zero
        # information about what actually broke. Now it comes back as a
        # real, readable detail string.
        raise HTTPException(status_code=500, detail=f"Could not load worker profile: {e}") from e