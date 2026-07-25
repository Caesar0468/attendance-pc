# app/main.py
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database import init_db
from app.config import ensure_dirs, BASE_DIR
from app.services.backup_service import BackupService

from app.routers import (
    upload,
    attendance,
    workers,
    reports,
    pair,
    system,
    auth,
    calendar,
    gallery,
    backup,
    sync,
    gdrive,
    audit,
)

# Must run before app.mount() below
ensure_dirs()
(BASE_DIR / "static").mkdir(parents=True, exist_ok=True)


async def background_backup_task():
    """Runs a native SQLite snapshot every 15 minutes to prevent data loss."""
    while True:
        await asyncio.sleep(15 * 60)
        try:
            BackupService.snapshot_db(reason="auto")
        except Exception as e:
            print(f"Auto-backup failed: {e}")


async def background_sync_task():
    """Every 10 minutes, if a sync folder is configured, push then pull —
    push first so this device's own changes are visible before pulling
    others', keeping the exchange roughly symmetric each cycle."""
    while True:
        await asyncio.sleep(10 * 60)
        try:
            from app.services.sync_service import SyncService
            status = SyncService.get_status()
            if status["configured"]:
                SyncService.push()
                SyncService.pull()
        except Exception as e:
            print(f"Auto-sync failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dirs()
    (BASE_DIR / "static").mkdir(parents=True, exist_ok=True)

    init_db()

    task = asyncio.create_task(background_backup_task())
    sync_task = asyncio.create_task(background_sync_task())

    yield

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    sync_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        pass

    try:
        BackupService.snapshot_db(reason="shutdown")
    except Exception as e:
        print(f"Shutdown backup failed: {e}")


app = FastAPI(lifespan=lifespan, title="Attendance-PC v2")

from fastapi import Request
from fastapi.responses import JSONResponse
import logging, traceback

logger = logging.getLogger(__name__)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Any route that throws an uncaught exception used to return Starlette's
    default HTML/plain-text 500 page. The frontend's api() helper tries to
    res.json() every error response, which threw on that non-JSON body,
    swallowing the real reason and always showing a generic toast. Return
    JSON here so the actual cause always makes it to the UI."""
    logger.error("Unhandled exception on %s %s", request.method, request.url.path)
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})

app.include_router(auth.router)
app.include_router(upload.router)
app.include_router(attendance.router)
app.include_router(workers.router)
app.include_router(reports.router)
app.include_router(pair.router)
app.include_router(system.router)
app.include_router(calendar.router)
app.include_router(gallery.router)
app.include_router(backup.router)
app.include_router(sync.router)
app.include_router(gdrive.router)
app.include_router(audit.router)

app.mount("/photos", StaticFiles(directory=(BASE_DIR / "photos").as_posix()), name="photos")
app.mount("/uploads", StaticFiles(directory=(BASE_DIR / "uploads").as_posix()), name="uploads")
app.mount("/static", StaticFiles(directory=(BASE_DIR / "static").as_posix()), name="static")


@app.get("/")
def serve_dashboard():
    index_path = BASE_DIR / "static" / "index.html"
    if index_path.exists():
        return FileResponse(index_path.as_posix())
    return {"message": "Attendance API running. UI not found in static/."}


# BUGFIX: app/routers/system.py's /api/server-info and /api/qr-code both
# build the mobile pairing URL as ".../pair" (no ".html"), but previously
# only "/pair.html" was ever served here. Scanning the QR code or opening
# the pairing link from the dashboard 404'd. Serve both paths.
@app.get("/pair")
@app.get("/pair.html")
def serve_pair_page():
    pair_path = BASE_DIR / "static" / "pair.html"
    if pair_path.exists():
        return FileResponse(pair_path.as_posix())
    return {"message": "pair.html UI not found in static/."}