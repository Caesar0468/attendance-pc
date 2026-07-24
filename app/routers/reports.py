import sqlite3
from datetime import date

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
def create_report(body: ReportGenerateRequest):
    try:
        date.fromisoformat(body.start_date)
        date.fromisoformat(body.end_date)
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail="Invalid date format. Use YYYY-MM-DD."
        ) from e

    try:
        path = generate_report(body.start_date, body.end_date, body.daily_wage)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Could not generate the report. Please try again.",
        ) from e

    return {"filename": path.name, "download_url": f"/api/reports/download/{path.name}"}

@router.get("/download/{filename}")
def download_report(filename: str):
    # Resolve against REPORTS_DIR and verify the result is still inside it,
    # rather than trying to blacklist traversal sequences by string-replace
    # (which can be bypassed by crafted filenames).
    candidate = (REPORTS_DIR / filename).resolve()
    reports_root = REPORTS_DIR.resolve()

    if reports_root not in candidate.parents and candidate != reports_root:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail="Report file not found.")

    return FileResponse(
        candidate,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=candidate.name,
    )