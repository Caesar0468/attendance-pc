# app/services/backup_service.py
from __future__ import annotations

import sqlite3
import zipfile
import shutil
from pathlib import Path
from datetime import datetime

from app.config import BASE_DIR, DB_PATH, PHOTOS_DIR, UPLOADS_DIR

BACKUPS_DIR = BASE_DIR / "backups"
STAGING_DIR = BASE_DIR / "temp_staging"

# BUGFIX: snapshot_db() used to only ever clean up files matching
# "*_auto.db" (the periodic 15-minute snapshots). Every "export" snapshot
# (taken on every manual backup AND on every sync push()) and every
# "pre_import_rollback" snapshot (taken on every restore/pull) was written
# to disk and never deleted. Worse, export_package() also left a full
# attendance_export_*.zip (containing every photo in the system) behind on
# every single call, and with folder-sync running push() every 10 minutes,
# that meant a full photo-library zip accumulating on disk forever. All
# snapshot/export kinds are now bounded.
_DB_RETENTION = {
    "auto": 20,
    "export": 5,
    "pre_import_rollback": 5,
}
_ZIP_RETENTION = 10


class BackupService:
    @staticmethod
    def _cleanup(pattern: str, keep: int) -> None:
        files = sorted(BACKUPS_DIR.glob(pattern), key=lambda p: p.stat().st_mtime)
        stale = files[:-keep] if keep > 0 else files
        for old in stale:
            old.unlink(missing_ok=True)

    @staticmethod
    def snapshot_db(reason: str = "auto") -> Path:
        """Creates a corruption-free snapshot of the live database using SQLite native backup API."""
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_path = BACKUPS_DIR / f"attendance_{ts}_{reason}.db"

        src = sqlite3.connect(DB_PATH)
        dest = sqlite3.connect(dest_path)
        with dest:
            src.backup(dest)
        src.close()
        dest.close()

        keep = _DB_RETENTION.get(reason, 5)
        BackupService._cleanup(f"*_{reason}.db", keep)

        return dest_path

    @staticmethod
    def export_package() -> Path:
        """Creates a .zip bundle containing the DB snapshot, photos, and uploads."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = BACKUPS_DIR / f"attendance_export_{ts}.zip"

        # 1. Snapshot DB safely
        db_snapshot = BackupService.snapshot_db(reason="export")

        # 2. Package it up
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(db_snapshot, "attendance.db")
            for photo in PHOTOS_DIR.rglob("*"):
                if photo.is_file():
                    zf.write(photo, photo.relative_to(BASE_DIR).as_posix())
            for upload in UPLOADS_DIR.rglob("*"):
                if upload.is_file():
                    zf.write(upload, upload.relative_to(BASE_DIR).as_posix())

        # BUGFIX: bound how many export zips accumulate in BACKUPS_DIR.
        BackupService._cleanup("attendance_export_*.zip", _ZIP_RETENTION)

        return zip_path

    @staticmethod
    def import_package(zip_path: Path) -> None:
        """Safely unpacks a sync package into staging, validates it, and replaces live data."""
        if STAGING_DIR.exists():
            shutil.rmtree(STAGING_DIR)
        STAGING_DIR.mkdir(parents=True)

        # 1. Extract to isolated staging
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(STAGING_DIR)

        staging_db = STAGING_DIR / "attendance.db"
        if not staging_db.exists():
            raise ValueError("Invalid bundle: Missing attendance.db")

        # 2. Validate integrity before destroying local data
        conn = sqlite3.connect(staging_db)
        is_ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
        conn.close()
        if is_ok != "ok":
            raise ValueError("Corrupted database bundle.")

        # 3. Create rollback point of CURRENT data
        BackupService.snapshot_db(reason="pre_import_rollback")

        # 4. Swap database & remove WAL sidecars to prevent corruption
        for sidecar in (DB_PATH.parent / f"{DB_PATH.name}-wal", DB_PATH.parent / f"{DB_PATH.name}-shm"):
            if sidecar.exists():
                try:
                    sidecar.unlink()
                except Exception:
                    pass

        shutil.copy2(staging_db, DB_PATH)

        # 5. Merge Photos non-destructively
        staging_photos = STAGING_DIR / "photos"
        if staging_photos.exists():
            for item in staging_photos.rglob("*"):
                if item.is_file():
                    dest = PHOTOS_DIR / item.relative_to(staging_photos)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest)

        # 6. Merge Uploads (Thumbnails & Crops) non-destructively
        staging_uploads = STAGING_DIR / "uploads"
        if staging_uploads.exists():
            for item in staging_uploads.rglob("*"):
                if item.is_file():
                    dest = UPLOADS_DIR / item.relative_to(staging_uploads)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest)

        shutil.rmtree(STAGING_DIR)