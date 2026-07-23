import json
import sqlite3
from contextlib import contextmanager
from datetime import date
from typing import Any

from app.config import DB_PATH, ensure_dirs

VALID_SESSIONS = ("morning", "evening")

def init_db() -> None:
    ensure_dirs()
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS workers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                embeddings TEXT NOT NULL,
                thumbnail_path TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                morning_present INTEGER NOT NULL DEFAULT 0,
                evening_present INTEGER NOT NULL DEFAULT 0,
                confirmed_by TEXT,
                UNIQUE(worker_id, date),
                FOREIGN KEY (worker_id) REFERENCES workers(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS photos_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                uploader_username TEXT,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                session TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS uncertain_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                session TEXT NOT NULL,
                face_crop_path TEXT NOT NULL,
                suggested_worker_id INTEGER,
                similarity REAL,
                status TEXT NOT NULL DEFAULT 'pending',
                confirmed_worker_id INTEGER,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (suggested_worker_id) REFERENCES workers(id) ON DELETE SET NULL,
                FOREIGN KEY (confirmed_worker_id) REFERENCES workers(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date);
            CREATE INDEX IF NOT EXISTS idx_photos_log_date ON photos_log(date);
            """
        )
        # Initialize default settings if they don't exist
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('daily_wage', '500.0')"
        )

@contextmanager
def get_connection():
    """Legacy context manager for backwards compatibility.
    
    Deprecated: Use get_db() FastAPI dependency instead.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def get_db():
    """FastAPI dependency that yields a database connection.
    
    The connection is opened at the start of the request and closed
    when the request completes. FastAPI handles the lifecycle automatically.
    
    Usage:
        @router.get("/endpoint")
        def endpoint(db: sqlite3.Connection = Depends(get_db)):
            rows = db.execute("SELECT * FROM table").fetchall()
            return {"data": [dict(r) for r in rows]}
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)

def parse_embeddings(raw: str) -> list[list[float]]:
    return json.loads(raw)

def dumps_embeddings(embeddings: list[list[float]]) -> str:
    return json.dumps(embeddings)

def get_setting(key: str, default: str = "", db: sqlite3.Connection | None = None) -> str:
    """Get a setting value from the database.
    
    Args:
        key: Setting key to fetch
        default: Default value if key not found
        db: Optional database connection (uses get_connection if not provided)
    """
    if db is None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else default
    else:
        row = db.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

def set_setting(key: str, value: str, db: sqlite3.Connection | None = None) -> None:
    """Set a setting value in the database.
    
    Args:
        key: Setting key to set
        value: Setting value
        db: Optional database connection (uses get_connection if not provided)
    """
    if db is None:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
    else:
        db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

def ensure_attendance_row(worker_id: int, day: str, db: sqlite3.Connection) -> None:
    """Ensure an attendance row exists for the given worker and date.
    
    Args:
        worker_id: Worker ID
        day: Date string (YYYY-MM-DD)
        db: Database connection
    """
    db.execute(
        """
        INSERT OR IGNORE INTO attendance (worker_id, date, morning_present, evening_present)
        VALUES (?, ?, 0, 0)
        """,
        (worker_id, day),
    )

def mark_present(
    worker_id: int,
    day: str,
    session: str,
    confirmed_by: str = "auto",
    db: sqlite3.Connection | None = None,
) -> None:
    """Mark a worker as present for a session.
    
    Args:
        worker_id: Worker ID
        day: Date string (YYYY-MM-DD)
        session: 'morning' or 'evening'
        confirmed_by: Who confirmed the attendance ('auto' or 'manual')
        db: Optional database connection (uses get_connection if not provided)
    """
    if session not in VALID_SESSIONS:
        raise ValueError(f"Invalid session '{session}', expected 'morning' or 'evening'")

    column = "morning_present" if session == "morning" else "evening_present"
    
    if db is None:
        with get_connection() as conn:
            ensure_attendance_row(worker_id, day, conn)
            conn.execute(
                f"""
                UPDATE attendance
                SET {column} = 1, confirmed_by = ?
                WHERE worker_id = ? AND date = ?
                """,
                (confirmed_by, worker_id, day),
            )
    else:
        ensure_attendance_row(worker_id, day, db)
        db.execute(
            f"""
            UPDATE attendance
            SET {column} = 1, confirmed_by = ?
            WHERE worker_id = ? AND date = ?
            """,
            (confirmed_by, worker_id, day),
        )

def get_today_attendance(day: str | None = None, db: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Get attendance data for a specific day.
    
    Args:
        day: Date string (YYYY-MM-DD), defaults to today
        db: Optional database connection (uses get_connection if not provided)
    
    Returns:
        Dict with date, morning/evening lists, uncertain matches, and total workers
    """
    today = day or date.today().isoformat()
    
    if db is None:
        with get_connection() as conn:
            workers = conn.execute(
                "SELECT id, name, thumbnail_path FROM workers ORDER BY name"
            ).fetchall()
            attendance_rows = {
                row["worker_id"]: dict(row)
                for row in conn.execute(
                    "SELECT * FROM attendance WHERE date = ?", (today,)
                ).fetchall()
            }
            uncertain = [
                dict(row)
                for row in conn.execute(
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
    else:
        workers = db.execute(
            "SELECT id, name, thumbnail_path FROM workers ORDER BY name"
        ).fetchall()
        attendance_rows = {
            row["worker_id"]: dict(row)
            for row in db.execute(
                "SELECT * FROM attendance WHERE date = ?", (today,)
            ).fetchall()
        }
        uncertain = [
            dict(row)
            for row in db.execute(
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
                {"id": worker["id"], "name": worker["name"], "thumbnail_path": worker["thumbnail_path"]}
            )
        if att.get("evening_present"):
            evening_present.append(
                {"id": worker["id"], "name": worker["name"], "thumbnail_path": worker["thumbnail_path"]}
            )

    return {
        "date": today,
        "morning": morning_present,
        "evening": evening_present,
        "uncertain": uncertain,
        "total_workers": len(workers),
    }