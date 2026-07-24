from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel

from app.schemas.attendance import TodayAttendanceOut


class PhotoUploadOut(BaseModel):
    saved: bool
    filename: str
    faces_detected: int
    matched: List[int]
    uncertain: List[int]
    today: TodayAttendanceOut
    message: Optional[str] = None