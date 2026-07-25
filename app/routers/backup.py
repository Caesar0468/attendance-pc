# app/routers/backup.py
"""Exposes BackupService over HTTP.

BUGFIX: BackupService.export_package()/import_package() existed in
app/services/backup_service.py but were never wired up to any route, so the
backup/restore feature was completely unreachable from the running app.
This router fixes that.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.auth import get_current_user, require_manager_or_root, require_root
from app.services.backup_service import BackupService

router = APIRouter(prefix="/api/backup", tags=["Backup"])


@router.get("/export")
def export_backup(user: dict = Depends(require_root)):
    """Downloads a .zip bundle containing a DB snapshot, photos, and uploads.
    Restricted to root: this bundle contains everything, including all
    workers' face embeddings and every attendance photo."""
    try:
        zip_path = BackupService.export_package()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not create backup: {e}") from e
    return FileResponse(zip_path, filename=zip_path.name, media_type="application/zip")


@router.post("/import")
def import_backup(file: UploadFile = File(...), user: dict = Depends(require_root)):
    """Restores the app's data from a previously exported .zip bundle.
    Restricted to root: this can fully overwrite the live database."""
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Please upload a .zip backup bundle.")

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            tmp.write(file.file.read())
            tmp_path = Path(tmp.name)

        BackupService.import_package(tmp_path)
        return {
            "success": True,
            "message": "Backup restored successfully. Restart the app to ensure a clean reload.",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Restore failed: {e}") from e
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)