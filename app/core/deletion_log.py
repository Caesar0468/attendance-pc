# app/core/deletion_log.py
from __future__ import annotations

import json
import sqlite3


def log_deletion(
    db: sqlite3.Connection,
    entity_type: str,
    entity_id: str,
    deleted_by: str,
    reason: str,
    extra: dict | None = None,
) -> None:
    """Records who deleted what, when, and why. Call this BEFORE the actual
    delete happens so the log entry survives even if the delete itself fails
    partway through (e.g. DB row removed but file unlink throws)."""
    db.execute(
        "INSERT INTO deletion_audit_log (entity_type, entity_id, deleted_by, reason, extra) VALUES (?, ?, ?, ?, ?)",
        (entity_type, entity_id, deleted_by, reason, json.dumps(extra) if extra else None),
    )