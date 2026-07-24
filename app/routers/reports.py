import sqlite3
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.config import REPORTS_DIR
from app.database import get_db
from app.repositories.settings_repository import SettingsRepository
from app.report_generator import generate_report
from app.schemas import ReportGenerateOut, ReportGenerateRequest, ReportSettingsOut, SettingsUpdateRequest

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/settings", response_model=ReportSettingsOut)
def get_settings(db: sqlite3.Connection = Depends(get_db)):
    repo = SettingsRepository(db)
    stored_wage = repo.get("daily_wage", "500.0")
    return {"daily_wage": float(stored_wage)}


@router.post("/settings", response_model=ReportSettingsOut)
def update_settings(
    body: SettingsUpdateRequest,
    db: sqlite3.Connection = Depends(get_db),
):
    if body.daily_wage <= 0:
        raise HTTPException(
            status_code=400, detail="Daily wage must be greater than zero."
        )
    repo = SettingsRepository(db)
    repo.set("daily_wage", str(body.daily_wage))
    return {"daily_wage": body.daily_wage}


@router.post("/generate", response_model=ReportGenerateOut)
def generate_attendance_report(body: ReportGenerateRequest):
    try:
        datetime.strptime(body.start_date, "%Y-%m-%d")
        datetime.strptime(body.end_date, "%Y-%m-%d")
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail="Invalid date format. Use YYYY-MM-DD."
        ) from e

    try:
        report_path = generate_report(body.start_date, body.end_date, body.daily_wage)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Could not generate the report."
        ) from e

    return {"filename": report_path.name, "download_url": f"/api/reports/download/{report_path.name}"}


@router.get("/download/{filename}")
def download_report(filename: str):
    safe_filename = Path(filename).name
    file_path = REPORTS_DIR / safe_filename
    if not file_path.resolve().is_relative_to(REPORTS_DIR.resolve()) or not file_path.exists():
        raise HTTPException(status_code=404, detail="Report not found.")
    return FileResponse(file_path, filename=safe_filename)