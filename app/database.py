from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
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
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('daily_wage', '500.0')"
        )


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


def parse_embeddings(raw_json: str) -> list[list[float]]:
    try:
        data = json.loads(raw_json)
        if isinstance(data, list) and data and isinstance(data[0], (int, float)):
            return [data]
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def dumps_embeddings(embeddings: list[list[float]]) -> str:
    return json.dumps(embeddings)


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None