import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.database import get_connection
from app.face_service import FaceService
from app.repositories.attendance_repository import AttendanceRepository
from app.repositories.worker_repository import WorkerRepository
from app.schemas import ConfirmUncertainOut, ConfirmUncertainRequest, TodayAttendanceOut
from app.services.attendance_service import AttendanceService
from app.services.storage_service import StorageService
from app.ws_manager import manager

router = APIRouter(prefix="/api/today", tags=["today"])

@router.get("", response_model=TodayAttendanceOut)
def today_view(
    day: str | None = None,
    attendance_repo: AttendanceRepository = Depends(AttendanceRepository),
    worker_repo: WorkerRepository = Depends(WorkerRepository),
    storage: StorageService = Depends(StorageService),
    face_service: FaceService = Depends(FaceService.get),
):
    service = AttendanceService(
        storage, face_service, attendance_repo, worker_repo, manager
    )
    return service.get_today_attendance_summary(day)

@router.post("/confirm", response_model=ConfirmUncertainOut)
async def confirm_uncertain(
    body: ConfirmUncertainRequest,
    attendance_repo: AttendanceRepository = Depends(AttendanceRepository),
    worker_repo: WorkerRepository = Depends(WorkerRepository),
    storage: StorageService = Depends(StorageService),
    face_service: FaceService = Depends(FaceService.get),
):
    service = AttendanceService(
        storage, face_service, attendance_repo, worker_repo, manager
    )
    return await service.confirm_or_discard_uncertain_match(body)

@router.websocket("/ws")
async def today_websocket(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        with get_connection() as conn:
            repo = AttendanceRepository(conn)
            await websocket.send_json(
                {"type": "attendance_update", "data": repo.get_today_attendance()}
            )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
