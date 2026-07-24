"""Repository for worker data access operations"""
import sqlite3
from typing import Any

from fastapi import Depends

from app.database import dumps_embeddings, get_db, parse_embeddings


class WorkerRepository:
    """Handles all database operations related to workers"""

    def __init__(self, db: sqlite3.Connection = Depends(get_db)):
        self.db = db

    def get_all(self) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT id, name, thumbnail_path, created_at FROM workers ORDER BY name"
        ).fetchall()
        return [dict(row) for row in rows]

    def get_by_id(self, worker_id: int) -> dict[str, Any] | None:
        row = self.db.execute(
            "SELECT * FROM workers WHERE id = ?", (worker_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_all_with_embeddings(self) -> list[tuple[int, list[list[float]]]]:
        rows = self.db.execute("SELECT id, embeddings FROM workers").fetchall()
        return [
            (row["id"], parse_embeddings(row["embeddings"]))
            for row in rows
        ]

    def create(
        self,
        name: str,
        embeddings: list[list[float]],
        thumbnail_path: str | None,
    ) -> int:
        cur = self.db.execute(
            "INSERT INTO workers (name, embeddings, thumbnail_path) VALUES (?, ?, ?)",
            (name, dumps_embeddings(embeddings), thumbnail_path),
        )
        return cur.lastrowid

    def update(
        self,
        worker_id: int,
        name: str,
        embeddings: list[list[float]],
        thumbnail_path: str | None,
    ) -> None:
        self.db.execute(
            "UPDATE workers SET name = ?, embeddings = ?, thumbnail_path = ? WHERE id = ?",
            (name, dumps_embeddings(embeddings), thumbnail_path, worker_id),
        )

    def delete(self, worker_id: int) -> tuple[bool, str | None]:
        """Delete a worker by ID.

        Returns:
            Tuple of (found, thumbnail_path)
        """
        row = self.db.execute(
            "SELECT thumbnail_path FROM workers WHERE id = ?", (worker_id,)
        ).fetchone()

        if not row:
            return False, None

        self.db.execute("DELETE FROM workers WHERE id = ?", (worker_id,))
        return True, row["thumbnail_path"]

    def name_exists(self, name: str, exclude_id: int | None = None) -> bool:
        if exclude_id is not None:
            row = self.db.execute(
                "SELECT 1 FROM workers WHERE LOWER(name) = LOWER(?) AND id != ?",
                (name, exclude_id),
            ).fetchone()
        else:
            row = self.db.execute(
                "SELECT 1 FROM workers WHERE LOWER(name) = LOWER(?)",
                (name,),
            ).fetchone()
        return row is not None

    def exists(self, worker_id: int) -> bool:
        row = self.db.execute(
            "SELECT 1 FROM workers WHERE id = ?", (worker_id,)
        ).fetchone()
        return row is not None