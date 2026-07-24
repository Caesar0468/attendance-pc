from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.config import load_config
from app.face_service import FaceService
from app.repositories.worker_repository import WorkerRepository
from app.schemas import SuccessResponse, WorkerCreateOut, WorkerListOut
from app.services.storage_service import StorageService
from app.services.worker_service import WorkerService

router = APIRouter(prefix="/api/workers", tags=["workers"])


@router.get("", response_model=WorkerListOut)
def list_workers(worker_repo: WorkerRepository = Depends(WorkerRepository)):
    workers = worker_repo.get_all()
    return {"workers": workers}


@router.post("", response_model=WorkerCreateOut)
async def create_worker(
    name: str = Form(...),
    photos: list[UploadFile] = File(...),
    storage: StorageService = Depends(StorageService),
    face_svc: FaceService = Depends(FaceService.get),
    worker_repo: WorkerRepository = Depends(WorkerRepository),
):
    config = load_config()

    service = WorkerService(storage, face_svc, worker_repo)

    return await service.enroll_worker(
        name=name,
        photos=photos,
        min_photos=config["photos_per_worker_min"],
        max_photos=config["photos_per_worker_max"],
    )


@router.put("/{worker_id}", response_model=WorkerCreateOut)
async def update_worker(
    worker_id: int,
    name: str | None = Form(default=None),
    photos: list[UploadFile] | None = File(default=None),
    storage: StorageService = Depends(StorageService),
    face_svc: FaceService = Depends(FaceService.get),
    worker_repo: WorkerRepository = Depends(WorkerRepository),
):
    service = WorkerService(storage, face_svc, worker_repo)

    return await service.update_worker(
        worker_id=worker_id,
        name=name,
        photos=photos,
    )


@router.delete("/{worker_id}", response_model=SuccessResponse)
def delete_worker(
    worker_id: int,
    storage: StorageService = Depends(StorageService),
    face_svc: FaceService = Depends(FaceService.get),
    worker_repo: WorkerRepository = Depends(WorkerRepository),
):
    service = WorkerService(storage, face_svc, worker_repo)
    service.delete_worker_and_thumbnail(worker_id)
    return {"success": True}