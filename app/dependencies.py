# app/dependencies.py
from __future__ import annotations

from fastapi import Depends
from app.face_service import FaceService
from app.repositories.attendance_repository import AttendanceRepository
from app.repositories.worker_repository import WorkerRepository
from app.services.attendance_service import AttendanceService
from app.services.storage_service import StorageService
from app.ws_manager import manager


def get_attendance_service(
    attendance_repo: AttendanceRepository = Depends(AttendanceRepository),
    worker_repo: WorkerRepository = Depends(WorkerRepository),
    storage: StorageService = Depends(StorageService),
    face_service: FaceService = Depends(FaceService.get),
) -> AttendanceService:
    return AttendanceService(
        storage=storage,
        face_service=face_service,
        attendance_repo=attendance_repo,
        worker_repo=worker_repo,
        ws_manager=manager,
    )