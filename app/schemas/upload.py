"""Pydantic schemas for photo upload requests and responses"""

from pydantic import BaseModel

from app.schemas.attendance import TodayAttendanceOut

class PhotoUploadOut(BaseModel):
    """Response after uploading an attendance photo"""

    saved: bool
    filename: str
    faces_detected: int
    matched: list[int]  # List of worker IDs that were matched
    uncertain: list[int]  # List of uncertain match IDs created
    today: TodayAttendanceOut
    message: str | None = None  # Only present when no faces detected