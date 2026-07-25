# app/routers/gallery.py
from __future__ import annotations

import sqlite3
from fastapi import APIRouter, Depends, HTTPException
from app.database import get_db
from app.config import PHOTOS_DIR
from app.core.auth import get_current_user, require_manager_or_root
from app.core.deletion_log import log_deletion
from app.repositories.attendance_repository import AttendanceRepository
from app.schemas.attendance import DeleteReasonRequest
from app.ws_manager import manager

router = APIRouter(prefix="/api/gallery", tags=["Gallery"])


@router.get("", response_model=list[dict])
def list_photos(
    date: str | None = None, session: str | None = None,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    query = "SELECT * FROM photos_log WHERE 1=1"
    params = []
    if date:
        query += " AND date = ?"
        params.append(date)
    if session:
        query += " AND session = ?"
        params.append(session)
    query += " ORDER BY date DESC, time DESC"
    rows = db.execute(query, params).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["url"] = f"/photos/{d['date']}/{d['session']}/{d['filename']}"
        results.append(d)
    return results


@router.get("/{photo_id}/faces", response_model=list[dict])
def get_photo_matched_faces(photo_id: int, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        """
        SELECT f.bbox, f.similarity, w.name, w.thumbnail_path
        FROM attendance_faces f JOIN workers w ON f.worker_id = w.id
        WHERE f.photo_log_id = ?
        """,
        (photo_id,),
    ).fetchall()
    return [dict(r) for r in rows]


@router.delete("/{photo_id}")
async def delete_photo(
    photo_id: int,
    body: DeleteReasonRequest,
    user: dict = Depends(require_manager_or_root),
    db: sqlite3.Connection = Depends(get_db),
):
    """Deletes a photo and its DB record.

    BUGFIX: this used to only delete photos_log (which cascades
    attendance_faces via FK) and stop there. If a photo was the ONLY piece
    of evidence a worker was marked present for a given date/session, that
    worker stayed marked "present" forever with zero evidence backing it —
    a silent payroll-accuracy bug. Deleting a photo now also reverts
    attendance for any worker whose presence had no OTHER supporting photo
    for that same date/session, and logs the revert in
    attendance_audit_log so it's traceable. Workers with a second photo
    proving the same session are left untouched.
    """
    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="A reason is required to delete a photo.")
    row = db.execute("SELECT * FROM photos_log WHERE id = ?", (photo_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Photo not found.")

    # Log BEFORE deleting so the record survives even if file removal fails.
    log_deletion(
        db, entity_type="photo", entity_id=str(photo_id),
        deleted_by=user["username"], reason=body.reason.strip(),
        extra={"filename": row["filename"], "date": row["date"], "session": row["session"]},
    )

    # Find every worker whose presence was backed by THIS photo, before the
    # FK cascade wipes the attendance_faces rows that prove it.
    affected = db.execute(
        "SELECT DISTINCT worker_id, date, session FROM attendance_faces WHERE photo_log_id = ?",
        (photo_id,),
    ).fetchall()

    reverted: list[dict] = []
    for a in affected:
        # If some OTHER photo also proves this worker was present that
        # session, don't touch attendance — only revert when this photo
        # was the sole piece of evidence.
        other_evidence = db.execute(
            "SELECT COUNT(*) c FROM attendance_faces WHERE worker_id=? AND date=? AND session=? AND photo_log_id != ?",
            (a["worker_id"], a["date"], a["session"], photo_id),
        ).fetchone()["c"]
        if other_evidence > 0:
            continue

        field = "morning_present" if a["session"] == "morning" else "evening_present"
        cur = db.execute(
            f"SELECT {field} FROM attendance WHERE worker_id=? AND date=?",
            (a["worker_id"], a["date"]),
        ).fetchone()
        if cur and cur[field]:
            db.execute(
                f"UPDATE attendance SET {field}=0 WHERE worker_id=? AND date=?",
                (a["worker_id"], a["date"]),
            )
            db.execute(
                """INSERT INTO attendance_audit_log
                   (worker_id, date, field, old_value, new_value, changed_by, reason)
                   VALUES (?, ?, ?, 1, 0, ?, ?)""",
                (
                    a["worker_id"], a["date"], field, user["username"],
                    f"Auto-reverted: evidence photo deleted ({body.reason.strip()})",
                ),
            )
            reverted.append({"worker_id": a["worker_id"], "date": a["date"], "session": a["session"]})

    # Any attendance_faces rows referencing this photo cascade-delete via FK.
    db.execute("DELETE FROM photos_log WHERE id = ?", (photo_id,))

    file_path = PHOTOS_DIR / row["date"] / row["session"] / row["filename"]
    if file_path.exists():
        file_path.unlink(missing_ok=True)

    if reverted:
        repo = AttendanceRepository(db)
        await manager.broadcast({"type": "attendance_update", "data": repo.get_today_attendance()})

    return {"success": True, "attendance_reverted": reverted}