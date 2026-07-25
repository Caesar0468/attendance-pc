# app/routers/sync.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import require_root
from app.services.sync_service import SyncService

router = APIRouter(prefix="/api/sync", tags=["Sync"])


class SyncFolderRequest(BaseModel):
    folder: str


@router.get("/status")
def sync_status(user: dict = Depends(require_root)):
    return SyncService.get_status()


@router.post("/configure")
def configure_sync(body: SyncFolderRequest, user: dict = Depends(require_root)):
    if not body.folder.strip():
        raise HTTPException(status_code=400, detail="Folder path cannot be empty.")
    SyncService.set_folder(body.folder.strip())
    return {"success": True}


@router.post("/push")
def sync_push(user: dict = Depends(require_root)):
    try:
        return SyncService.push()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/pull")
def sync_pull(user: dict = Depends(require_root)):
    try:
        return SyncService.pull()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e