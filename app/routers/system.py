import io
import os
import signal
import threading

import qrcode
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app.config import get_local_ip, load_config
from app.schemas import HealthOut, ServerInfoOut, ShutdownOut

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health", response_model=HealthOut)
def health():
    return {"status": "ok"}


@router.get("/server-info", response_model=ServerInfoOut)
def server_info():
    config = load_config()
    local_ip = get_local_ip()
    port = config["port"]
    pair_url = f"http://{local_ip}:{port}/pair"
    return {
        "local_ip": local_ip,
        "port": port,
        "pair_url": pair_url,
        "app_url": f"http://localhost:{port}",
    }


@router.get("/qr-code")
def qr_code():
    config = load_config()
    local_ip = get_local_ip()
    pair_url = f"http://{local_ip}:{config['port']}/pair"
    img = qrcode.make(pair_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


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