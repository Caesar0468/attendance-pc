# app/routers/gdrive.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.core.auth import require_root
from app.services.gdrive_service import GDriveNotConfigured, GDriveService

router = APIRouter(prefix="/api/gdrive", tags=["Google Drive"])


class ClientCredentialsRequest(BaseModel):
    client_id: str
    client_secret: str


@router.get("/status")
def gdrive_status(user: dict = Depends(require_root)):
    return GDriveService.status()


@router.post("/credentials")
def set_credentials(body: ClientCredentialsRequest, user: dict = Depends(require_root)):
    if not body.client_id.strip() or not body.client_secret.strip():
        raise HTTPException(status_code=400, detail="Both client ID and client secret are required.")
    GDriveService.set_client_credentials(body.client_id, body.client_secret)
    return {"success": True}


@router.get("/connect")
def connect(user: dict = Depends(require_root)):
    try:
        auth_url = GDriveService.start_auth()
    except GDriveNotConfigured as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"auth_url": auth_url}


@router.get("/oauth-callback", response_class=HTMLResponse)
def oauth_callback(code: str | None = None, state: str | None = None, error: str | None = None):
    # Google redirects the browser here directly, so this request carries no
    # session cookie and can't require login the normal way. It's protected
    # instead by the random `state` value minted in start_auth() and
    # checked in finish_auth() — only a state we ourselves generated for a
    # logged-in root's connect click will be accepted.
    if error:
        return f"<html><body style='font-family:sans-serif'><h3>Google Drive connection failed: {error}</h3><p>You can close this tab.</p></body></html>"
    if not code or not state:
        return "<html><body style='font-family:sans-serif'><h3>Missing authorization code.</h3><p>You can close this tab.</p></body></html>"
    try:
        GDriveService.finish_auth(code, state)
    except Exception as e:
        return f"<html><body style='font-family:sans-serif'><h3>Could not complete Google Drive connection.</h3><p>{e}</p></body></html>"
    return "<html><body style='font-family:sans-serif'><h3>Google Drive connected ✅</h3><p>You can close this tab and go back to the dashboard.</p></body></html>"


@router.post("/disconnect")
def disconnect(user: dict = Depends(require_root)):
    GDriveService.disconnect()
    return {"success": True}


@router.post("/push")
def push(user: dict = Depends(require_root)):
    try:
        return GDriveService.push()
    except GDriveNotConfigured as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google Drive push failed: {e}") from e


@router.post("/pull")
def pull(user: dict = Depends(require_root)):
    try:
        return GDriveService.pull()
    except GDriveNotConfigured as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google Drive pull failed: {e}") from e