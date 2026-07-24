"""Pydantic schemas for request/response validation across the application"""

from app.schemas.attendance import (
    ConfirmUncertainOut,
    ConfirmUncertainRequest,
    TodayAttendanceOut,
    UncertainMatchItem,
    WorkerAttendanceItem,
)
from app.schemas.common import MessageResponse, SuccessResponse
from app.schemas.report import (
    ReportGenerateOut,
    ReportGenerateRequest,
    ReportSettingsOut,
    SettingsUpdateRequest,
)
from app.schemas.system import (
    HealthOut,
    PairDeviceOut,
    PairDeviceRequest,
    ServerInfoOut,
    ShutdownOut,
)
from app.schemas.upload import PhotoUploadOut
from app.schemas.worker import (
    WorkerBase,
    WorkerCreateOut,
    WorkerListOut,
    WorkerOut,
    WorkerWithTimestamp,
)

__all__ = [
    # Common
    "MessageResponse",
    "SuccessResponse",
    # Workers
    "WorkerBase",
    "WorkerCreateOut",
    "WorkerListOut",
    "WorkerOut",
    "WorkerWithTimestamp",
    # Attendance
    "ConfirmUncertainOut",
    "ConfirmUncertainRequest",
    "TodayAttendanceOut",
    "UncertainMatchItem",
    "WorkerAttendanceItem",
    # Upload
    "PhotoUploadOut",
    # Reports
    "ReportGenerateOut",
    "ReportGenerateRequest",
    "ReportSettingsOut",
    "SettingsUpdateRequest",
    # System
    "HealthOut",
    "PairDeviceOut",
    "PairDeviceRequest",
    "ServerInfoOut",
    "ShutdownOut",
]