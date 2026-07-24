"""Service for handling file system operations"""
import uuid
from datetime import datetime
from pathlib import Path

from app.config import BASE_DIR, PHOTOS_DIR, UPLOADS_DIR
from app.exif_utils import embed_exif

class StorageService:
    """Handles all file system operations for photos, thumbnails, and crops"""
    
    def __init__(self):
        self.photos_dir = PHOTOS_DIR
        self.uploads_dir = UPLOADS_DIR
        self.base_dir = BASE_DIR
    
    def save_attendance_photo(
        self,
        image_bytes: bytes,
        username: str,
        date: str,
        timestamp: str,
        session: str
    ) -> tuple[Path, str]:
        """Save an attendance photo with EXIF data embedded
        
        Args:
            image_bytes: Raw image data
            username: Uploader's username
            date: Date string (YYYY-MM-DD)
            timestamp: ISO timestamp string
            session: 'morning' or 'evening'
            
        Returns:
            Tuple of (absolute_path, relative_filename_for_db)
        """
        # Parse time from timestamp for filename
        try:
            dt = self._datetime_from_timestamp(timestamp)
            time_str = dt.strftime("%H%M%S")
        except Exception:
            time_str = "000000"
        
        session_id = uuid.uuid4().hex[:8]
        filename = f"{username}_{date}_{time_str}_{session_id}.jpg"
        
        save_dir = self.photos_dir / date / session
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / filename
        
        # Embed EXIF data
        try:
            exif_bytes = embed_exif(image_bytes, username, timestamp)
        except Exception:
            exif_bytes = image_bytes
        
        save_path.write_bytes(exif_bytes)
        
        # Return relative path for database storage
        relative_path = str(save_path.relative_to(self.photos_dir.parent))
        return save_path, relative_path
    
    def save_worker_thumbnail(self, thumbnail_bytes: bytes) -> tuple[Path, str]:
        """Save a worker thumbnail image
        
        Args:
            thumbnail_bytes: Processed thumbnail image bytes
            
        Returns:
            Tuple of (absolute_path, relative_path_for_db)
        """
        thumb_name = f"{uuid.uuid4().hex}.jpg"
        thumb_dir = self.uploads_dir / "thumbnails"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        
        thumb_path = thumb_dir / thumb_name
        thumb_path.write_bytes(thumbnail_bytes)
        
        # Return relative path like "uploads/thumbnails/abc123.jpg"
        return thumb_path, f"uploads/thumbnails/{thumb_name}"
    
    def delete_thumbnail(self, thumbnail_path: str | None) -> None:
        """Delete a thumbnail file
        
        Args:
            thumbnail_path: Relative path like "uploads/thumbnails/abc123.jpg"
        """
        if not thumbnail_path:
            return
        
        thumb_file = self.uploads_dir / "thumbnails" / Path(thumbnail_path).name
        thumb_file.unlink(missing_ok=True)
    
    def save_uncertain_crop(self, crop_bytes: bytes) -> tuple[Path, str]:
        """Save a face crop for an uncertain match
        
        Args:
            crop_bytes: Cropped face image bytes
            
        Returns:
            Tuple of (absolute_path, relative_path_for_db)
        """
        crop_name = f"{uuid.uuid4().hex}.jpg"
        uncertain_dir = self.base_dir / "uploads" / "uncertain"
        uncertain_dir.mkdir(parents=True, exist_ok=True)
        
        crop_path = uncertain_dir / crop_name
        crop_path.write_bytes(crop_bytes)
        
        # Return relative path like "uploads/uncertain/xyz789.jpg"
        return crop_path, f"uploads/uncertain/{crop_name}"
    
    @staticmethod
    def _datetime_from_timestamp(timestamp: str) -> datetime:
        """Parse various timestamp formats
        
        Args:
            timestamp: Timestamp string in various formats
            
        Returns:
            datetime object
        """
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S.%fZ",
        ):
            try:
                return datetime.strptime(timestamp.replace("Z", ""), fmt.replace("Z", ""))
            except ValueError:
                continue
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))