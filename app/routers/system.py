from __future__ import annotations

import io
import os
import signal
import sqlite3
import threading

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from app.config import get_local_ip, load_config
from app.core.auth import issue_pair_token, require_manager_or_root
from app.database import get_db
from app.schemas import HealthOut, ServerInfoOut, ShutdownOut

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health", response_model=HealthOut)
def health():
    return {"status": "ok"}


@router.get("/server-info", response_model=ServerInfoOut)
def server_info(
    user: dict = Depends(require_manager_or_root),
    db: sqlite3.Connection = Depends(get_db),
):
    """Mints ONE pairing token and returns it both embedded in pair_url and
    as its own pair_token field. The frontend must pass that same
    pair_token straight through to /api/qr-code so the visible URL text and
    the scanned QR image always agree on the same token.

    BUGFIX: previously this endpoint and /api/qr-code each independently
    called issue_pair_token(), silently minting TWO different tokens per
    "Pair Mobile" modal open. Both were individually valid so it usually
    "worked", but copy-pasting the visible URL instead of scanning the QR
    (or any regenerate/race scenario) could hand out a token that didn't
    match what the QR pointed to, causing spurious "No pairing token found"
    style failures on the phone.
    """
    config = load_config()
    local_ip = get_local_ip()
    port = config["port"]
    token = issue_pair_token(db, created_by=user["username"])
    pair_url = f"http://{local_ip}:{port}/pair.html?token={token}"
    return {
        "local_ip": local_ip,
        "port": port,
        "pair_url": pair_url,
        "app_url": f"http://localhost:{port}",
        "pair_token": token,
    }


@router.get("/qr-code")
def qr_code(
    token: str | None = None,
    user: dict = Depends(require_manager_or_root),
    db: sqlite3.Connection = Depends(get_db),
):
    """Renders a QR code for the pairing URL.

    BUGFIX: now accepts an optional `token` query param so the frontend can
    pass through the exact token it already got from /api/server-info,
    guaranteeing the QR image and the on-screen URL text point at the SAME
    pairing session. Only mints a fresh token here as a fallback if none is
    supplied (keeps this endpoint usable standalone).
    """
    config = load_config()
    local_ip = get_local_ip()
    if not token:
        token = issue_pair_token(db, created_by=user["username"])
    pair_url = f"http://{local_ip}:{config['port']}/pair.html?token={token}"
    img = qrcode.make(pair_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(
        content=buf.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/shutdown", response_model=ShutdownOut)
def shutdown_server(request: Request):
    """Stop the server (used by Quit button or stop_app.bat).
    Restricted to loopback calls to prevent unauthenticated network DoS.
    """
    client_host = request.client.host if request.client else ""
    if client_host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(
            status_code=403, detail="Shutdown is only allowed from localhost."
        )

    def _stop():
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Timer(0.5, _stop).start()
    return {"success": True, "message": "Application is closing."}