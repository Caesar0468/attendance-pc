# app/database.py
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Callable

from app.config import DB_PATH, ensure_dirs

VALID_SESSIONS = ("morning", "evening")
SCHEMA_VERSION = 6


# --- EMBEDDING SERIALIZATION HELPERS ---
def dumps_embeddings(embeddings: list[list[float]]) -> str:
    """Serializes floating-point face embeddings to JSON for SQLite storage."""
    return json.dumps(embeddings)


def parse_embeddings(raw: str) -> list[list[float]]:
    """Parses JSON-encoded face embeddings back into Python float lists."""
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return []


# --- SCHEMA VERSIONING ---
def _get_schema_version(conn: sqlite3.Connection) -> int:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    row = conn.execute("SELECT value FROM schema_meta WHERE key='version'").fetchone()
    return int(row["value"]) if row else 0


def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        "INSERT INTO schema_meta (key, value) VALUES ('version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(version),),
    )


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    try:
        return any(row["name"] == column for row in conn.execute(f"PRAGMA table_info({table})"))
    except sqlite3.OperationalError:
        return False


# --- SAFE MIGRATIONS ---
def _migration_001_batch_and_sync(conn: sqlite3.Connection) -> None:
    if not _column_exists(conn, "photos_log", "batch_id"):
        conn.execute("ALTER TABLE photos_log ADD COLUMN batch_id TEXT")
    if not _column_exists(conn, "uncertain_matches", "batch_id"):
        conn.execute("ALTER TABLE uncertain_matches ADD COLUMN batch_id TEXT")
    if not _column_exists(conn, "uncertain_matches", "embedding"):
        conn.execute("ALTER TABLE uncertain_matches ADD COLUMN embedding TEXT")


def _migration_002_calendar_notes(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS day_notes (
            date TEXT PRIMARY KEY,
            note TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_by TEXT
        )
    """)


def _migration_003_audit_log(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS attendance_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            field TEXT NOT NULL,
            old_value INTEGER,
            new_value INTEGER,
            changed_by TEXT NOT NULL,
            reason TEXT,
            changed_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (worker_id) REFERENCES workers(id) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_worker_date ON attendance_audit_log(worker_id, date)")


def _migration_004_auth(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'admin',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)


def _migration_005_attendance_faces(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS attendance_faces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            session TEXT NOT NULL,
            photo_log_id INTEGER NOT NULL,
            bbox TEXT NOT NULL,
            similarity REAL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (worker_id) REFERENCES workers(id) ON DELETE CASCADE,
            FOREIGN KEY (photo_log_id) REFERENCES photos_log(id) ON DELETE CASCADE
        )
    """)


def _migration_006_uncertain_match_photo_ref(conn: sqlite3.Connection) -> None:
    """Adds photo_log_id/bbox to uncertain_matches so manually-confirmed
    matches can still be linked into attendance_faces for report photo
    evidence (previously that link was silently dropped)."""
    if not _column_exists(conn, "uncertain_matches", "photo_log_id"):
        conn.execute("ALTER TABLE uncertain_matches ADD COLUMN photo_log_id INTEGER")
    if not _column_exists(conn, "uncertain_matches", "bbox"):
        conn.execute("ALTER TABLE uncertain_matches ADD COLUMN bbox TEXT")


def _migration_007_deletion_log(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS deletion_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            deleted_by TEXT NOT NULL,
            reason TEXT NOT NULL,
            extra TEXT,
            deleted_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_deletion_type ON deletion_audit_log(entity_type, entity_id)")


def _migration_008_sync_state(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            direction TEXT NOT NULL,
            summary TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)


def _migration_009_pair_tokens(conn: sqlite3.Connection) -> None:
    """NEW: backs the mobile pairing-token auth flow. Worker enrollment and
    photo upload used to have zero auth on them; they now require either a
    logged-in session OR one of these short-lived tokens, which are only
    ever minted for a root/manager who is already logged into the
    dashboard (see app/core/auth.py:issue_pair_token and the Pair Mobile
    QR flow in app/routers/system.py)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pair_tokens (
            token TEXT PRIMARY KEY,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pair_tokens_expires ON pair_tokens(expires_at)")


MIGRATIONS: list[Callable[[sqlite3.Connection], None]] = [
    _migration_001_batch_and_sync,
    _migration_002_calendar_notes,
    _migration_003_audit_log,
    _migration_004_auth,
    _migration_005_attendance_faces,
    _migration_006_uncertain_match_photo_ref,
    _migration_007_deletion_log,
    _migration_008_sync_state,
    _migration_009_pair_tokens,
]


def run_migrations(conn: sqlite3.Connection) -> None:
    current = _get_schema_version(conn)
    for i, migration in enumerate(MIGRATIONS[current:], start=current + 1):
        migration(conn)
        _set_schema_version(conn, i)


def init_db() -> None:
    ensure_dirs()
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS workers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                embeddings TEXT NOT NULL,
                thumbnail_path TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                morning_present INTEGER DEFAULT 0,
                evening_present INTEGER DEFAULT 0,
                confirmed_by TEXT DEFAULT 'auto',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (worker_id) REFERENCES workers(id) ON DELETE CASCADE,
                UNIQUE(worker_id, date)
            );
            CREATE TABLE IF NOT EXISTS photos_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                uploader_username TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                session TEXT NOT NULL,
                uploaded_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS uncertain_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                session TEXT NOT NULL,
                face_crop_path TEXT NOT NULL,
                suggested_worker_id INTEGER,
                similarity REAL,
                status TEXT DEFAULT 'pending',
                confirmed_worker_id INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (suggested_worker_id) REFERENCES workers(id) ON DELETE SET NULL,
                FOREIGN KEY (confirmed_worker_id) REFERENCES workers(id) ON DELETE SET NULL
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('daily_wage', '500.0')")
        run_migrations(conn)
        # NOTE: no default admin account is seeded here anymore. First-run
        # setup is handled by GET /api/auth/setup-status + POST /api/auth/setup
        # in app/routers/auth.py — the app stays unusable until someone
        # creates a root account through that flow.

@contextmanager
def get_connection():
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_db():
    with get_connection() as conn:
        yield conn