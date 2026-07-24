from __future__ import annotations

import sqlite3
from datetime import date as date_type

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.exceptions import BaseAppException
from app.database import get_db
from app.face_service import FaceService
from app.repositories.attendance_repository import AttendanceRepository
from app.repositories.worker_repository import WorkerRepository
from app.schemas import PhotoUploadOut
from app.services.attendance_service import AttendanceService
from app.services.storage_service import StorageService
from app.ws_manager import manager

router = APIRouter(tags=["upload"])

VALID_SESSIONS = {"morning", "evening"}


@router.post("/upload-photo", response_model=PhotoUploadOut)
async def upload_photo(
    file: UploadFile = File(...),
    username: str = Form(...),
    session: str = Form(...),
    timestamp: str = Form(...),
    photo_date: str | None = Form(default=None, alias="date"),
    db: sqlite3.Connection = Depends(get_db),
):
    attendance_date = photo_date or date_type.today().isoformat()

    try:
        date_type.fromisoformat(attendance_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid date format.") from e

    clean_username = username.strip()
    if not clean_username:
        raise HTTPException(status_code=400, detail="Username is required.")

    clean_session = session.strip().lower()
    if clean_session not in VALID_SESSIONS:
        raise HTTPException(
            status_code=400, detail="Session must be 'morning' or 'evening'."
        )

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload an image file.")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file was empty.")

    storage = StorageService()
    face_svc = FaceService.get()
    attendance_repo = AttendanceRepository(db)
    worker_repo = WorkerRepository(db)

    service = AttendanceService(
        storage, face_svc, attendance_repo, worker_repo, manager
    )

    try:
        result = await service.process_attendance_photo(
            image_bytes=data,
            username=clean_username,
            session=clean_session,
            timestamp=timestamp.strip(),
            photo_date=attendance_date,
        )
    except BaseAppException as e:
        raise HTTPException(status_code=getattr(e, "status_code", 400), detail=e.detail) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail="Could not process that photo. Please try again.",
        ) from e

    return result