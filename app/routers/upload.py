# app/routers/upload.py
from __future__ import annotations

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from app.services.attendance_service import AttendanceService
from app.schemas.upload import PhotoUploadOut
from app.dependencies import get_attendance_service
from app.core.auth import require_pairing_or_user

router = APIRouter(prefix="/api", tags=["Upload"])

@router.post("/upload-photo", response_model=PhotoUploadOut)
async def upload_photo(
    file: UploadFile = File(...),
    username: str = Form(...),
    session: str = Form(...),
    timestamp: str = Form(...),
    date: str = Form(...),
    batch_id: str = Form(None),  # Optional Batch ID for Deduplication
    service: AttendanceService = Depends(get_attendance_service),
    # BUGFIX: this endpoint had no auth dependency at all — anyone on the
    # LAN could POST attendance photos as any username, or flood the queue.
    # It now requires either a dashboard login or a short-lived pairing
    # token (minted only via the logged-in Pair Mobile QR flow).
    user: dict = Depends(require_pairing_or_user),
):
    image_bytes = await file.read()

    try:
        result = await service.process_attendance_photo(
            image_bytes=image_bytes,
            username=username,
            session=session,
            timestamp=timestamp,
            photo_date=date,
            batch_id=batch_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))