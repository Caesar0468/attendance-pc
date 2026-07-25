# app/repositories/attendance_repository.py
from __future__ import annotations

import json
import sqlite3
import math
from datetime import date as date_type
from typing import Any

from fastapi import Depends
from app.database import VALID_SESSIONS, get_db


def _cosine_similarity(v1: list[float], v2: list[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    return dot / (mag1 * mag2) if mag1 * mag2 else 0.0


class AttendanceRepository:
    def __init__(self, db: sqlite3.Connection = Depends(get_db)):
        self.db = db

    def get_today_attendance(self, date: str | None = None) -> dict[str, Any]:
        today = date or date_type.today().isoformat()

        workers = self.db.execute(
            "SELECT id, name, thumbnail_path FROM workers ORDER BY name"
        ).fetchall()

        attendance_rows = {
            row["worker_id"]: dict(row)
            for row in self.db.execute("SELECT * FROM attendance WHERE date = ?", (today,)).fetchall()
        }

        uncertain = [
            dict(row)
            for row in self.db.execute("""
                SELECT u.*, w.name AS suggested_worker_name
                FROM uncertain_matches u
                LEFT JOIN workers w ON w.id = u.suggested_worker_id
                WHERE u.date = ? AND u.status = 'pending'
                ORDER BY u.created_at DESC
            """, (today,)).fetchall()
        ]

        morning_present = [
            {"id": w["id"], "name": w["name"], "thumbnail_path": w["thumbnail_path"]}
            for w in workers if attendance_rows.get(w["id"], {}).get("morning_present")
        ]
        evening_present = [
            {"id": w["id"], "name": w["name"], "thumbnail_path": w["thumbnail_path"]}
            for w in workers if attendance_rows.get(w["id"], {}).get("evening_present")
        ]

        return {
            "date": today,
            "morning": morning_present,
            "evening": evening_present,
            "uncertain": uncertain,
            "total_workers": len(workers)
        }

    def log_photo(self, filename: str, username: str, date: str, time: str, session: str, batch_id: str | None = None) -> int:
        cur = self.db.execute(
            "INSERT INTO photos_log (filename, uploader_username, date, time, session, batch_id) VALUES (?, ?, ?, ?, ?, ?)",
            (filename, username, date, time, session, batch_id),
        )
        return cur.lastrowid

    def ensure_attendance_row(self, worker_id: int, date: str) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO attendance (worker_id, date, morning_present, evening_present) VALUES (?, ?, 0, 0)",
            (worker_id, date),
        )

    def set_attendance_with_audit(
        self, worker_id: int, date: str, session: str, new_value: bool, changed_by: str, reason: str | None = None
    ) -> None:
        """Atomic operation: Updates attendance and records an immutable audit trail."""
        if session not in VALID_SESSIONS:
            raise ValueError(f"Invalid session '{session}'")

        self.ensure_attendance_row(worker_id, date)
        field = "morning_present" if session == "morning" else "evening_present"

        row = self.db.execute(
            f"SELECT {field} FROM attendance WHERE worker_id = ? AND date = ?",
            (worker_id, date)
        ).fetchone()
        old_value = bool(row[field]) if row else False

        self.db.execute(
            f"UPDATE attendance SET {field} = ?, confirmed_by = ? WHERE worker_id = ? AND date = ?",
            (int(new_value), "manual" if changed_by != "auto" else "auto", worker_id, date),
        )
        self.db.execute(
            """
            INSERT INTO attendance_audit_log (worker_id, date, field, old_value, new_value, changed_by, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (worker_id, date, field, int(old_value), int(new_value), changed_by, reason),
        )

    def mark_present(self, worker_id: int, date: str, session: str, confirmed_by: str = "auto") -> None:
        self.set_attendance_with_audit(worker_id, date, session, True, confirmed_by)

    def record_matched_face(self, worker_id: int, date: str, session: str, photo_log_id: int, bbox: list[int], similarity: float) -> None:
        self.db.execute(
            "INSERT INTO attendance_faces (worker_id, date, session, photo_log_id, bbox, similarity) VALUES (?, ?, ?, ?, ?, ?)",
            (worker_id, date, session, photo_log_id, json.dumps(bbox), similarity)
        )

    def is_duplicate_uncertain_in_batch(self, batch_id: str, new_embedding: list[float], threshold: float = 0.60) -> bool:
        """Checks if a similar unrecognized face is already pending in the current upload batch."""
        rows = self.db.execute(
            "SELECT embedding FROM uncertain_matches WHERE batch_id = ? AND status = 'pending'",
            (batch_id,)
        ).fetchall()

        for r in rows:
            if not r["embedding"]:
                continue
            stored_emb = json.loads(r["embedding"])
            if _cosine_similarity(new_embedding, stored_emb) >= threshold:
                return True
        return False

    def create_uncertain_match(
        self, date: str, session: str, face_crop_path: str, suggested_worker_id: int | None,
        similarity: float | None, batch_id: str | None = None, embedding: str | None = None,
        photo_log_id: int | None = None, bbox: list[float] | None = None,
    ) -> int:
        # BUGFIX: added photo_log_id/bbox so a manually-confirmed uncertain
        # match can still be linked into attendance_faces for report evidence.
        cur = self.db.execute(
            """
            INSERT INTO uncertain_matches
                (date, session, face_crop_path, suggested_worker_id, similarity, status, batch_id, embedding, photo_log_id, bbox)
            VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)
            """,
            (
                date, session, face_crop_path, suggested_worker_id, similarity, batch_id, embedding,
                photo_log_id, json.dumps(bbox) if bbox is not None else None,
            ),
        )
        return cur.lastrowid

    def get_uncertain_match(self, match_id: int) -> dict[str, Any] | None:
        row = self.db.execute("SELECT * FROM uncertain_matches WHERE id = ?", (match_id,)).fetchone()
        return dict(row) if row else None

    def update_uncertain_match_status(self, match_id: int, status: str, confirmed_worker_id: int | None) -> None:
        self.db.execute(
            "UPDATE uncertain_matches SET status = ?, confirmed_worker_id = ? WHERE id = ?",
            (status, confirmed_worker_id, match_id)
        )
