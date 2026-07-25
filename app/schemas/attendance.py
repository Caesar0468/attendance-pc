# app/schemas/attendance.py
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel


class WorkerAttendanceItem(BaseModel):
    worker_id: int
    name: str
    thumbnail_path: Optional[str] = None
    status: Optional[str] = None
    time: Optional[str] = None
    confirmed_by: Optional[str] = None


class UncertainMatchItem(BaseModel):
    id: int
    date: Optional[str] = None
    session: Optional[str] = None
    face_crop_path: Optional[str] = None
    suggested_worker_id: Optional[int] = None
    similarity: Optional[float] = None
    created_at: Optional[str] = None


class TodayAttendanceOut(BaseModel):
    date: str
    morning: list[dict[str, Any]]
    evening: list[dict[str, Any]]
    uncertain: list[dict[str, Any]]
    total_workers: int


class ConfirmUncertainRequest(BaseModel):
    match_id: int
    confirm: bool
    worker_id: Optional[int] = None


class ConfirmUncertainOut(BaseModel):
    success: bool
    status: str
    today: TodayAttendanceOut


class AttendanceOverrideRequest(BaseModel):
    worker_id: int
    date: str
    session: str  # "morning" or "evening"
    present: bool
    reason: str


class BulkOverrideRequest(BaseModel):
    worker_id: int
    start_date: str
    end_date: str
    session: str  # "morning", "evening", or "both"
    present: bool
    reason: str


class DeleteReasonRequest(BaseModel):
    reason: str


class NoteUpdateSchema(BaseModel):
    note: str


class CalendarDayOut(BaseModel):
    date: str
    morning_present: int
    evening_present: int
    note: Optional[str] = None