# app/services/storage_service.py
from __future__ import annotations

import re
import uuid
import io
import shutil
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from app.config import BASE_DIR, PHOTOS_DIR, UPLOADS_DIR, THUMBNAILS_DIR, CROPS_DIR
from app.exif_utils import embed_exif

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9_-]")


def _get_font(font_size: int) -> ImageFont.ImageFont:
    """Try a series of cross-platform font paths before falling back to PIL's
    tiny fixed-size default font, which ignores font_size entirely and made
    watermark text unreadable on Linux/macOS where arial.ttf isn't installed.
    """
    font_candidates = [
        "arial.ttf",
        "Arial.ttf",
        "DejaVuSans-Bold.ttf",
        "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for font_name in font_candidates:
        try:
            return ImageFont.truetype(font_name, font_size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _apply_mandatory_watermark(image_bytes: bytes, username: str, date_str: str, time_str: str) -> bytes:
    """Burns watermark into image pixels. Fails hard if error occurs (no fallback)."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    text = f"User: {username} | Date: {date_str} | Time: {time_str}"
    font_size = max(18, img.height // 35)
    font = _get_font(font_size)

    padding = 12
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x, y = padding, img.height - text_h - padding * 2

    # Dark semi-transparent background strip at bottom for legibility
    draw.rectangle([0, img.height - text_h - (padding * 2), img.width, img.height], fill=(0, 0, 0, 160))
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))

    watermarked = Image.alpha_composite(img, overlay).convert("RGB")

    out = io.BytesIO()
    watermarked.save(out, format="JPEG", quality=92)
    result = out.getvalue()
    if not result:
        raise RuntimeError("Watermarking resulted in zero bytes.")
    return result


class StorageService:
    def __init__(self):
        self.photos_dir = PHOTOS_DIR
        self.uploads_dir = UPLOADS_DIR
        self.thumbnails_dir = THUMBNAILS_DIR
        self.crops_dir = CROPS_DIR
        self.base_dir = BASE_DIR

        for d in [self.photos_dir, self.uploads_dir, self.thumbnails_dir, self.crops_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def _datetime_from_timestamp(self, ts_str: str) -> datetime:
        try:
            return datetime.fromtimestamp(int(ts_str) / 1000)
        except (ValueError, TypeError):
            pass
        try:
            return datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
        except (ValueError, TypeError, AttributeError):
            return datetime.now()

    def save_attendance_photo(self, image_bytes: bytes, username: str, date: str, timestamp: str, session: str) -> tuple[Path, str]:
        safe_username = _SAFE_CHARS.sub("_", username)[:50] or "unknown"
        try:
            dt = self._datetime_from_timestamp(timestamp)
            time_str = dt.strftime("%H%M%S")
        except Exception:
            time_str = "000000"

        watermarked_bytes = _apply_mandatory_watermark(image_bytes, safe_username, date, time_str)

        session_id = uuid.uuid4().hex[:8]
        filename = f"{safe_username}_{date}_{time_str}_{session_id}.jpg"
        save_dir = self.photos_dir / date / session
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / filename

        try:
            final_bytes = embed_exif(watermarked_bytes, username, timestamp)
        except Exception:
            final_bytes = watermarked_bytes

        save_path.write_bytes(final_bytes)

        # BUGFIX: this used to return save_path.relative_to(photos_dir.parent),
        # i.e. "photos/<date>/<session>/<filename>". gallery.py and
        # report_generator.py already prepend "/photos/<date>/<session>/" to
        # whatever is stored in photos_log.filename, so storing the full
        # relative path produced duplicated, broken paths like
        # "/photos/2026-07-25/morning/photos/2026-07-25/morning/x.jpg".
        # Store just the bare filename instead; callers reconstruct the path.
        return save_path, save_path.name

    def save_worker_thumbnail(self, worker_name: str, face_bytes: bytes) -> tuple[Path, str]:
        safe_name = _SAFE_CHARS.sub("_", worker_name)[:50]
        filename = f"{safe_name}_{uuid.uuid4().hex[:8]}.jpg"
        save_path = self.thumbnails_dir / filename
        save_path.write_bytes(face_bytes)
        relative_path = save_path.relative_to(self.uploads_dir.parent).as_posix()
        return save_path, relative_path

    def save_uncertain_crop(self, face_bytes: bytes) -> tuple[Path, str]:
        filename = f"uncertain_{uuid.uuid4().hex[:12]}.jpg"
        save_path = self.crops_dir / filename
        save_path.write_bytes(face_bytes)
        relative_path = save_path.relative_to(self.uploads_dir.parent).as_posix()
        return save_path, relative_path

    def delete_thumbnail(self, relative_path: str) -> None:
        if relative_path:
            path = self.base_dir / relative_path
            if path.exists():
                path.unlink(missing_ok=True)
