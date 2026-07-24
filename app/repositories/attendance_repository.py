"""Repository for attendance and uncertain match data access operations"""
import sqlite3
from datetime import date as date_type
from typing import Any

from app.database import VALID_SESSIONS

class AttendanceRepository:
    """Handles all database operations related to attendance tracking"""
    
    def __init__(self, db: sqlite3.Connection):
        self.db = db
    
    def ensure_attendance_row(self, worker_id: int, date: str) -> None:
        """Ensure an attendance row exists for the given worker and date
        
        Args:
            worker_id: Worker ID
            date: Date string (YYYY-MM-DD)
        """
        self.db.execute(
            """
            INSERT OR IGNORE INTO attendance (worker_id, date, morning_present, evening_present)
            VALUES (?, ?, 0, 0)
            """,
            (worker_id, date),
        )
    
    def mark_present(
        self,
        worker_id: int,
        date: str,
        session: str,
        confirmed_by: str = "auto"
    ) -> None:
        """Mark a worker as present for a session
        
        Args:
            worker_id: Worker ID
            date: Date string (YYYY-MM-DD)
            session: 'morning' or 'evening'
            confirmed_by: Who confirmed the attendance ('auto' or 'manual')
        """
        if session not in VALID_SESSIONS:
            raise ValueError(f"Invalid session '{session}', expected 'morning' or 'evening'")
        
        self.ensure_attendance_row(worker_id, date)
        
        column = "morning_present" if session == "morning" else "evening_present"
        self.db.execute(
            f"""
            UPDATE attendance
            SET {column} = 1, confirmed_by = ?
            WHERE worker_id = ? AND date = ?
            """,
            (confirmed_by, worker_id, date),
        )
    
    def get_today_attendance(self, date: str | None = None) -> dict[str, Any]:
        """Get attendance data for a specific day
        
        Args:
            date: Date string (YYYY-MM-DD), defaults to today
        
        Returns:
            Dict with date, morning/evening lists, uncertain matches, and total workers
        """
        today = date or date_type.today().isoformat()
        
        workers = self.db.execute(
            "SELECT id, name, thumbnail_path FROM workers ORDER BY name"
        ).fetchall()
        
        attendance_rows = {
            row["worker_id"]: dict(row)
            for row in self.db.execute(
                "SELECT * FROM attendance WHERE date = ?", (today,)
            ).fetchall()
        }
        
        uncertain = [
            dict(row)
            for row in self.db.execute(
                """
                SELECT u.*, w.name AS suggested_worker_name
                FROM uncertain_matches u
                LEFT JOIN workers w ON w.id = u.suggested_worker_id
                WHERE u.date = ? AND u.status = 'pending'
                ORDER BY u.created_at DESC
                """,
                (today,),
            ).fetchall()
        ]
        
        morning_present = []
        evening_present = []
        for worker in workers:
            att = attendance_rows.get(worker["id"], {})
            if att.get("morning_present"):
                morning_present.append(
                    {
                        "id": worker["id"],
                        "name": worker["name"],
                        "thumbnail_path": worker["thumbnail_path"]
                    }
                )
            if att.get("evening_present"):
                evening_present.append(
                    {
                        "id": worker["id"],
                        "name": worker["name"],
                        "thumbnail_path": worker["thumbnail_path"]
                    }
                )
        
        return {
            "date": today,
            "morning": morning_present,
            "evening": evening_present,
            "uncertain": uncertain,
            "total_workers": len(workers),
        }
    
    def log_photo(
        self,
        filename: str,
        username: str,
        date: str,
        time: str,
        session: str
    ) -> None:
        """Log an uploaded photo to the photos_log table
        
        Args:
            filename: Photo filename/path
            username: Uploader's username
            date: Date string (YYYY-MM-DD)
            time: Time string (HHMMSS)
            session: 'morning' or 'evening'
        """
        self.db.execute(
            """
            INSERT INTO photos_log (filename, uploader_username, date, time, session)
            VALUES (?, ?, ?, ?, ?)
            """,
            (filename, username, date, time, session),
        )
    
    def get_uncertain_by_id(self, uncertain_id: int) -> dict[str, Any] | None:
        """Get a pending uncertain match by ID
        
        Args:
            uncertain_id: ID of uncertain match
            
        Returns:
            Uncertain match dict or None if not found
        """
        row = self.db.execute(
            "SELECT * FROM uncertain_matches WHERE id = ? AND status = 'pending'",
            (uncertain_id,),
        ).fetchone()
        return dict(row) if row else None
    
    def discard_uncertain(self, uncertain_id: int) -> None:
        """Mark an uncertain match as discarded
        
        Args:
            uncertain_id: ID of uncertain match to discard
        """
        self.db.execute(
            "UPDATE uncertain_matches SET status = 'discarded' WHERE id = ?",
            (uncertain_id,),
        )
    
    def confirm_uncertain(self, uncertain_id: int, worker_id: int) -> None:
        """Confirm an uncertain match with a specific worker
        
        Args:
            uncertain_id: ID of uncertain match
            worker_id: ID of worker to confirm
        """
        self.db.execute(
            """
            UPDATE uncertain_matches
            SET status = 'confirmed', confirmed_worker_id = ?
            WHERE id = ?
            """,
            (worker_id, uncertain_id),
        )
    
    def create_uncertain_match(
        self,
        date: str,
        session: str,
        face_crop_path: str,
        suggested_worker_id: int | None,
        similarity: float | None
    ) -> int:
        """Create a new uncertain match entry
        
        Args:
            date: Date string (YYYY-MM-DD)
            session: 'morning' or 'evening'
            face_crop_path: Path to cropped face image
            suggested_worker_id: ID of suggested worker (if any)
            similarity: Similarity score (if any)
            
        Returns:
            ID of the newly created uncertain match
        """
        cur = self.db.execute(
            """
            INSERT INTO uncertain_matches
                (date, session, face_crop_path, suggested_worker_id, similarity, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
            """,
            (date, session, face_crop_path, suggested_worker_id, similarity),
        )
        return cur.lastrowid