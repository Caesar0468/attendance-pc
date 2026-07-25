# app/schemas/__init__.py
from __future__ import annotations

from app.schemas.attendance import (
    BulkOverrideRequest,
    ConfirmUncertainOut,
    ConfirmUncertainRequest,
    DeleteReasonRequest,
    TodayAttendanceOut,
    UncertainMatchItem,
    WorkerAttendanceItem,
)
from app.schemas.common import SuccessResponse
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
    "WorkerAttendanceItem",
    "UncertainMatchItem",
    "TodayAttendanceOut",
    "ConfirmUncertainRequest",
    "ConfirmUncertainOut",
    "BulkOverrideRequest",
    "DeleteReasonRequest",
    "WorkerBase",
    "WorkerOut",
    "WorkerWithTimestamp",
    "WorkerCreateOut",
    "WorkerListOut",
    "PhotoUploadOut",
    "ReportSettingsOut",
    "SettingsUpdateRequest",
    "ReportGenerateRequest",
    "ReportGenerateOut",
    "HealthOut",
    "ServerInfoOut",
    "ShutdownOut",
    "PairDeviceRequest",
    "PairDeviceOut",
    "SuccessResponse",
]