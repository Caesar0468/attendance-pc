# app/routers/calendar.py
from __future__ import annotations

import sqlite3
from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import get_current_user, require_manager_or_root, require_root
from app.database import get_db
from app.schemas.attendance import NoteUpdateSchema

router = APIRouter(prefix="/api/calendar", tags=["Calendar"])


@router.get("/day/{date}", response_model=dict)
def get_day_summary(date: str, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    """Gets attendance totals and the operational note for a specific day."""
    note_row = db.execute("SELECT note FROM day_notes WHERE date = ?", (date,)).fetchone()
    note_text = note_row["note"] if note_row else ""

    att_rows = db.execute(
        "SELECT sum(morning_present) as am, sum(evening_present) as pm FROM attendance WHERE date = ?", (date,)
    ).fetchone()

    return {
        "date": date,
        "note": note_text,
        "morning_total": att_rows["am"] or 0,
        "evening_total": att_rows["pm"] or 0,
    }


@router.put("/day/{date}/note", response_model=dict)
def update_day_note(
    date: str,
    body: NoteUpdateSchema,
    user: dict = Depends(require_manager_or_root),
    db: sqlite3.Connection = Depends(get_db),
):
    """Upserts a daily operational note (e.g., 'Rained out')."""
    db.execute(
        """
        INSERT INTO day_notes (date, note, updated_by)
        VALUES (?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET note = excluded.note, updated_at = datetime('now'), updated_by = excluded.updated_by
        """,
        (date, body.note, user["username"]),
    )
    return {"success": True, "date": date, "note": body.note}