"""Pydantic schemas for attendance and today view requests and responses"""

from pydantic import BaseModel


class WorkerAttendanceItem(BaseModel):
    id: int
    name: str
    thumbnail_path: str | None


class UncertainMatchItem(BaseModel):
    id: int
    date: str
    session: str
    face_crop_path: str
    suggested_worker_id: int | None
    similarity: float | None
    status: str
    confirmed_worker_id: int | None
    created_at: str | None = None
    suggested_worker_name: str | None


class TodayAttendanceOut(BaseModel):
    date: str
    morning: list[WorkerAttendanceItem]
    evening: list[WorkerAttendanceItem]
    uncertain: list[UncertainMatchItem]
    total_workers: int


class ConfirmUncertainRequest(BaseModel):
    uncertain_id: int
    worker_id: int | None = None


class ConfirmUncertainOut(BaseModel):
    success: bool
    today: TodayAttendanceOut