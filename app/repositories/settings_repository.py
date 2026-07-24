"""Repository for application settings data access operations"""
import sqlite3

class SettingsRepository:
    """Handles all database operations related to application settings"""
    
    def __init__(self, db: sqlite3.Connection):
        self.db = db
    
    def get(self, key: str, default: str = "") -> str:
        """Get a setting value from the database
        
        Args:
            key: Setting key to fetch
            default: Default value if key not found
            
        Returns:
            Setting value or default
        """
        row = self.db.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default
    
    def set(self, key: str, value: str) -> None:
        """Set a setting value in the database
        
        Args:
            key: Setting key to set
            value: Setting value
        """
        self.db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )