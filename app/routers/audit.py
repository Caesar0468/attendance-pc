# app/routers/audit.py
"""Exposes deletion_audit_log over HTTP.

BUGFIX: log_deletion() in app/core/deletion_log.py has always written every
worker/photo deletion (who, what, when, why) into deletion_audit_log — but
no route ever read that table back. The reasons captured on every delete
were being recorded and then never shown anywhere. This router fixes that.
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from app.core.auth import require_manager_or_root
from app.database import get_db

router = APIRouter(prefix="/api/audit", tags=["Audit"])


@router.get("/deletions")
def list_deletions(
    user: dict = Depends(require_manager_or_root),
    db: sqlite3.Connection = Depends(get_db),
):
    rows = db.execute(
        "SELECT * FROM deletion_audit_log ORDER BY deleted_at DESC LIMIT 200"
    ).fetchall()
    return {"entries": [dict(r) for r in rows]}