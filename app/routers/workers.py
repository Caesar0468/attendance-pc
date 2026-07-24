import sqlite3
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.config import load_config
from app.core.exceptions import BaseAppException
from app.database import get_db
from app.face_service import FaceService
from app.repositories.worker_repository import WorkerRepository
from app.schemas import SuccessResponse, WorkerCreateOut, WorkerListOut
from app.services.storage_service import StorageService
from app.services.worker_service import WorkerService

router = APIRouter(prefix="/api/workers", tags=["workers"])


@router.get("", response_model=WorkerListOut)
def list_workers(db: sqlite3.Connection = Depends(get_db)):
    worker_repo = WorkerRepository(db)
    workers = worker_repo.get_all()
    return {"workers": workers}


@router.post("", response_model=WorkerCreateOut)
async def create_worker(
    name: str = Form(...),
    photos: list[UploadFile] = File(...),
    db: sqlite3.Connection = Depends(get_db),
    storage: StorageService = Depends(StorageService),
    face_svc: FaceService = Depends(FaceService.get),
):
    config = load_config()
    worker_repo = WorkerRepository(db)
    service = WorkerService(storage, face_svc, worker_repo)

    try:
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
    db: sqlite3.Connection = Depends(get_db),
    storage: StorageService = Depends(StorageService),
    face_svc: FaceService = Depends(FaceService.get),
):
    worker_repo = WorkerRepository(db)
    service = WorkerService(storage, face_svc, worker_repo)

    try:
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
    db: sqlite3.Connection = Depends(get_db),
    storage: StorageService = Depends(StorageService),
    face_svc: FaceService = Depends(FaceService.get),
):
    worker_repo = WorkerRepository(db)
    service = WorkerService(storage, face_svc, worker_repo)

    try:
        service.delete_worker_and_thumbnail(worker_id)
        return {"success": True}
    except BaseAppException as e:
        raise HTTPException(status_code=getattr(e, "status_code", 400), detail=e.detail) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Could not delete worker.") from e