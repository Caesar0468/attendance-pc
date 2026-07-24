"""Service for handling file system operations"""
import re
import uuid
from datetime import datetime
from pathlib import Path

from app.config import BASE_DIR, PHOTOS_DIR, UPLOADS_DIR
from app.exif_utils import embed_exif

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9_-]")


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
        session: str,
    ) -> tuple[Path, str]:
        """Save an attendance photo with EXIF data embedded"""
        # Sanitize username to prevent path traversal attacks
        safe_username = _SAFE_CHARS.sub("_", username)[:50] or "unknown"

        try:
            dt = self._datetime_from_timestamp(timestamp)
            time_str = dt.strftime("%H%M%S")
        except Exception:
            time_str = "000000"

        session_id = uuid.uuid4().hex[:8]
        filename = f"{safe_username}_{date}_{time_str}_{session_id}.jpg"

        save_dir = self.photos_dir / date / session
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / filename

        try:
            exif_bytes = embed_exif(image_bytes, username, timestamp)
        except Exception:
            exif_bytes = image_bytes

        save_path.write_bytes(exif_bytes)

        # Enforce POSIX forward-slashes for web URL compatibility on Windows
        relative_path = save_path.relative_to(self.photos_dir.parent).as_posix()
        return save_path, relative_path

    def save_worker_thumbnail(self, thumbnail_bytes: bytes) -> tuple[Path, str]:
        thumb_name = f"{uuid.uuid4().hex}.jpg"
        thumb_dir = self.uploads_dir / "thumbnails"
        thumb_dir.mkdir(parents=True, exist_ok=True)

        thumb_path = thumb_dir / thumb_name
        thumb_path.write_bytes(thumbnail_bytes)

        return thumb_path, f"uploads/thumbnails/{thumb_name}"

    def delete_thumbnail(self, thumbnail_path: str | None) -> None:
        if not thumbnail_path:
            return

        thumb_file = self.uploads_dir / "thumbnails" / Path(thumbnail_path).name
        thumb_file.unlink(missing_ok=True)

    def save_uncertain_crop(self, crop_bytes: bytes) -> tuple[Path, str]:
        crop_name = f"{uuid.uuid4().hex}.jpg"
        uncertain_dir = self.base_dir / "uploads" / "uncertain"
        uncertain_dir.mkdir(parents=True, exist_ok=True)

        crop_path = uncertain_dir / crop_name
        crop_path.write_bytes(crop_bytes)

        return crop_path, f"uploads/uncertain/{crop_name}"

    @staticmethod
    def _datetime_from_timestamp(timestamp: str) -> datetime:
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