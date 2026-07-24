from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class ReportSettingsOut(BaseModel):
    daily_wage: float


class SettingsUpdateRequest(BaseModel):
    daily_wage: float


class ReportGenerateRequest(BaseModel):
    start_date: str
    end_date: str
    daily_wage: Optional[float] = None


class ReportGenerateOut(BaseModel):
    filename: str
    download_url: str