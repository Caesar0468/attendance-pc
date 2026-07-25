# app/schemas/upload.py
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel
from app.schemas.attendance import TodayAttendanceOut


class PhotoUploadOut(BaseModel):
    saved: bool
    filename: str
    faces_detected: int
    matched: list[int]
    uncertain: list[int]
    today: TodayAttendanceOut
    message: Optional[str] = None