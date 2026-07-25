from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class ReportSettingsOut(BaseModel):
    daily_wage: float


class SettingsUpdateRequest(BaseModel):
    daily_wage: float


# BUGFIX: this class used to be defined twice in this file (namespace
# shadowing). It happened to work at runtime because Python just keeps the
# second definition, which is this one with include_photos — but it was
# confusing and fragile. Now defined once.
class ReportGenerateRequest(BaseModel):
    start_date: str
    end_date: str
    daily_wage: Optional[float] = None
    include_photos: bool = True


class ReportGenerateOut(BaseModel):
    filename: str
    download_url: str
