# app/services/sync_service.py
from __future__ import annotations

import json
import shutil
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path

from app.config import BASE_DIR
from app.database import get_connection
from app.repositories.settings_repository import SettingsRepository
from app.services.backup_service import BackupService

SYNC_MANIFEST_NAME = "manifest.json"


class SyncService:
    @staticmethod
    def _get_folder(conn: sqlite3.Connection) -> Path | None:
        repo = SettingsRepository(conn)
        raw = repo.get("sync_folder_path", "")
        return Path(raw) if raw else None

    @staticmethod
    def get_status() -> dict:
        with get_connection() as conn:
            repo = SettingsRepository(conn)
            folder = repo.get("sync_folder_path", "")
            last_push = repo.get("last_push_at", "")
            last_pull = repo.get("last_pull_at", "")
            logs = conn.execute(
                "SELECT * FROM sync_log ORDER BY created_at DESC LIMIT 20"
            ).fetchall()
            pending_pull = 0
            if folder and Path(folder).exists():
                device_id = repo.get("device_id", "")
                for bundle_dir in sorted(Path(folder).glob("device_*")):
                    if bundle_dir.name != f"device_{device_id}":
                        manifest_path = bundle_dir / SYNC_MANIFEST_NAME
                        if manifest_path.exists():
                            try:
                                m = json.loads(manifest_path.read_text())
                                if m.get("exported_at", "") > (last_pull or ""):
                                    pending_pull += 1
                            except Exception:
                                pass
            return {
                "folder": folder,
                "configured": bool(folder),
                "last_push_at": last_push,
                "last_pull_at": last_pull,
                "pending_pull": pending_pull,
                "log": [dict(r) for r in logs],
            }

    @staticmethod
    def set_folder(path: str) -> None:
        with get_connection() as conn:
            repo = SettingsRepository(conn)
            repo.set("sync_folder_path", path)
            if not repo.get("device_id", ""):
                import uuid
                repo.set("device_id", uuid.uuid4().hex[:8])

    @staticmethod
    def push() -> dict:
        """Exports a full snapshot bundle into this device's own subfolder
        inside the sync folder. Never writes to the live .db — only ever
        writes finished, closed export bundles, matching the safe-sync rule."""
        with get_connection() as conn:
            repo = SettingsRepository(conn)
            folder = repo.get("sync_folder_path", "")
            if not folder:
                raise ValueError("No sync folder configured.")
            device_id = repo.get("device_id", "")
            if not device_id:
                import uuid
                device_id = uuid.uuid4().hex[:8]
                repo.set("device_id", device_id)

        sync_root = Path(folder)
        sync_root.mkdir(parents=True, exist_ok=True)
        device_dir = sync_root / f"device_{device_id}"
        device_dir.mkdir(parents=True, exist_ok=True)

        # Reuse the existing export mechanism — a corruption-free snapshot,
        # not the live file.
        zip_path = BackupService.export_package()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_zip = device_dir / f"sync_{ts}.zip"
        shutil.copy2(zip_path, dest_zip)

        # Keep only the latest bundle per device to avoid unbounded growth —
        # older ones are already superseded, this isn't the backup history.
        for old in sorted(device_dir.glob("sync_*.zip"))[:-1]:
            old.unlink(missing_ok=True)

        manifest = {"device_id": device_id, "exported_at": datetime.now().isoformat(), "bundle": dest_zip.name}
        (device_dir / SYNC_MANIFEST_NAME).write_text(json.dumps(manifest, indent=2))

        with get_connection() as conn:
            repo = SettingsRepository(conn)
            repo.set("last_push_at", datetime.now().isoformat())
            conn.execute(
                "INSERT INTO sync_log (direction, summary, status) VALUES ('push', ?, 'ok')",
                (f"Pushed snapshot to {device_dir.name}",),
            )
        return {"success": True, "pushed_to": str(dest_zip)}

    @staticmethod
    def pull() -> dict:
        """Imports the newest bundle from every OTHER device's subfolder.

        BUGFIX: this used to iterate `sorted(sync_root.glob("device_*"))`,
        which sorts by DEVICE-ID STRING, not by time. Since each import is a
        full database-file replace (not a per-row merge), importing an
        older bundle *after* a newer one silently threw away the newer
        changes with no error and no log entry pointing at it — a real risk
        for payroll-relevant attendance corrections with 3+ active devices.
        Candidates are now collected first and imported oldest-to-newest by
        their actual `exported_at` timestamp, so the final DB state always
        reflects the most recently exported bundle, exactly matching the
        "last write wins" comment this function already had.
        """
        with get_connection() as conn:
            repo = SettingsRepository(conn)
            folder = repo.get("sync_folder_path", "")
            device_id = repo.get("device_id", "")
            last_pull = repo.get("last_pull_at", "")
        if not folder:
            raise ValueError("No sync folder configured.")

        sync_root = Path(folder)
        if not sync_root.exists():
            raise ValueError("Sync folder does not exist or isn't accessible.")

        candidates: list[tuple[str, Path, dict]] = []
        for bundle_dir in sync_root.glob("device_*"):
            if bundle_dir.name == f"device_{device_id}":
                continue
            manifest_path = bundle_dir / SYNC_MANIFEST_NAME
            if not manifest_path.exists():
                continue
            try:
                m = json.loads(manifest_path.read_text())
            except Exception:
                continue
            exported_at = m.get("exported_at", "")
            if exported_at <= (last_pull or ""):
                continue
            bundle_path = bundle_dir / m.get("bundle", "")
            if not bundle_path.exists():
                continue
            candidates.append((exported_at, bundle_dir, m))

        # Oldest first, so the LAST import applied is the most recent one —
        # that's the state we end up on disk.
        candidates.sort(key=lambda c: c[0])

        imported = []
        for _exported_at, bundle_dir, m in candidates:
            bundle_path = bundle_dir / m.get("bundle", "")
            BackupService.import_package(bundle_path)
            imported.append(bundle_dir.name)

        with get_connection() as conn:
            repo = SettingsRepository(conn)
            repo.set("last_pull_at", datetime.now().isoformat())
            summary = f"Pulled from: {', '.join(imported)}" if imported else "Nothing new to pull"
            conn.execute(
                "INSERT INTO sync_log (direction, summary, status) VALUES ('pull', ?, 'ok')",
                (summary,),
            )
        return {"success": True, "imported_from": imported}