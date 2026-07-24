from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class WorkerAttendanceItem(BaseModel):
    id: int
    name: str
    thumbnail_path: Optional[str] = None


class UncertainMatchItem(BaseModel):
    id: int
    date: str
    session: str
    face_crop_path: str
    suggested_worker_id: Optional[int] = None
    similarity: Optional[float] = None
    status: str
    confirmed_worker_id: Optional[int] = None
    created_at: Optional[str] = None
    suggested_worker_name: Optional[str] = None


class TodayAttendanceOut(BaseModel):
    date: str
    morning: list[WorkerAttendanceItem]
    evening: list[WorkerAttendanceItem]
    uncertain: list[UncertainMatchItem]
    total_workers: int


class ConfirmUncertainRequest(BaseModel):
    uncertain_id: int
    worker_id: Optional[int] = None


class ConfirmUncertainOut(BaseModel):
    success: bool
    today: TodayAttendanceOut