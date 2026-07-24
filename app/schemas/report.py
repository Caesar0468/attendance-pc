"""Pydantic schemas for report generation and settings requests and responses"""

from pydantic import BaseModel

class ReportSettingsOut(BaseModel):
    """Daily wage settings output"""

    daily_wage: float

class SettingsUpdateRequest(BaseModel):
    """Request to update daily wage setting"""

    daily_wage: float

class ReportGenerateRequest(BaseModel):
    """Request to generate an attendance report"""

    start_date: str
    end_date: str
    daily_wage: float | None = None

class ReportGenerateOut(BaseModel):
    """Response after generating a report"""

    filename: str
    download_url: str