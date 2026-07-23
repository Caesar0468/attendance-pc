"""Pydantic schemas for attendance and today view requests and responses"""

from pydantic import BaseModel

class WorkerAttendanceItem(BaseModel):
    """Worker shown in attendance list (morning/evening)"""

    id: int
    name: str
    thumbnail_path: str | None

class UncertainMatchItem(BaseModel):
    """Uncertain face match requiring manual confirmation"""

    id: int
    date: str
    session: str
    face_crop_path: str
    suggested_worker_id: int | None
    similarity: float | None
    status: str
    confirmed_worker_id: int | None
    created_at: str
    suggested_worker_name: str | None

class TodayAttendanceOut(BaseModel):
    """Today's attendance summary with morning/evening lists and uncertain matches"""

    date: str
    morning: list[WorkerAttendanceItem]
    evening: list[WorkerAttendanceItem]
    uncertain: list[UncertainMatchItem]
    total_workers: int

class ConfirmUncertainRequest(BaseModel):
    """Request to confirm or discard an uncertain match"""

    uncertain_id: int
    worker_id: int | None = None  # None = not a worker (discard)

class ConfirmUncertainOut(BaseModel):
    """Response after confirming/discarding uncertain match"""

    success: bool
    today: TodayAttendanceOut