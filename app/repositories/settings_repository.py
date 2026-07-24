"""Repository for application settings data access operations"""
import sqlite3

from fastapi import Depends

from app.database import get_db


class SettingsRepository:
    """Handles all database operations related to application settings"""

    def __init__(self, db: sqlite3.Connection = Depends(get_db)):
        self.db = db

    def get(self, key: str, default: str = "") -> str:
        row = self.db.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set(self, key: str, value: str) -> None:
        self.db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )