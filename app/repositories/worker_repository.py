"""Repository for worker data access operations"""
import sqlite3
from typing import Any

from app.database import dumps_embeddings, parse_embeddings

class WorkerRepository:
    """Handles all database operations related to workers"""
    
    def __init__(self, db: sqlite3.Connection):
        self.db = db
    
    def get_all(self) -> list[dict[str, Any]]:
        """Get all workers with basic info (id, name, thumbnail, created_at)"""
        rows = self.db.execute(
            "SELECT id, name, thumbnail_path, created_at FROM workers ORDER BY name"
        ).fetchall()
        return [dict(row) for row in rows]
    
    def get_by_id(self, worker_id: int) -> dict[str, Any] | None:
        """Get a worker by ID with all fields"""
        row = self.db.execute(
            "SELECT * FROM workers WHERE id = ?", (worker_id,)
        ).fetchone()
        return dict(row) if row else None
    
    def get_all_with_embeddings(self) -> list[tuple[int, list[list[float]]]]:
        """Get all workers with their embeddings for face matching
        
        Returns:
            List of tuples: (worker_id, embeddings_list)
        """
        rows = self.db.execute("SELECT id, embeddings FROM workers").fetchall()
        return [
            (row["id"], parse_embeddings(row["embeddings"])) 
            for row in rows
        ]
    
    def create(
        self, 
        name: str, 
        embeddings: list[list[float]], 
        thumbnail_path: str | None
    ) -> int:
        """Create a new worker
        
        Args:
            name: Worker's name
            embeddings: List of face embeddings
            thumbnail_path: Path to thumbnail image
            
        Returns:
            ID of the newly created worker
        """
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
        thumbnail_path: str | None
    ) -> None:
        """Update an existing worker
        
        Args:
            worker_id: ID of worker to update
            name: New name
            embeddings: Updated embeddings list
            thumbnail_path: Updated thumbnail path
        """
        self.db.execute(
            "UPDATE workers SET name = ?, embeddings = ?, thumbnail_path = ? WHERE id = ?",
            (name, dumps_embeddings(embeddings), thumbnail_path, worker_id),
        )
    
    def delete(self, worker_id: int) -> str | None:
        """Delete a worker by ID
        
        Args:
            worker_id: ID of worker to delete
            
        Returns:
            The thumbnail_path of the deleted worker (for cleanup), or None if not found
        """
        row = self.db.execute(
            "SELECT thumbnail_path FROM workers WHERE id = ?", (worker_id,)
        ).fetchone()
        
        if not row:
            return None
        
        self.db.execute("DELETE FROM workers WHERE id = ?", (worker_id,))
        return row["thumbnail_path"]
    
    def exists(self, worker_id: int) -> bool:
        """Check if a worker exists
        
        Args:
            worker_id: ID to check
            
        Returns:
            True if worker exists, False otherwise
        """
        row = self.db.execute(
            "SELECT 1 FROM workers WHERE id = ?", (worker_id,)
        ).fetchone()
        return row is not None