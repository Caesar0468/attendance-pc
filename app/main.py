from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR, ensure_dirs, load_config
from app.database import init_db
from app.routers import attendance, pair, reports, system, upload, workers


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dirs()
    init_db()
    yield


app = FastAPI(title="Kshirsagar Group Attendance", lifespan=lifespan)

app.include_router(workers.router)
app.include_router(attendance.router)
app.include_router(reports.router)
app.include_router(pair.router)
app.include_router(upload.router)
app.include_router(system.router)

static_dir = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

uploads_dir = BASE_DIR / "uploads"
uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")


@app.get("/")
async def index():
    index_path = static_dir / "index.html"
    return FileResponse(index_path)


@app.get("/pair")
async def pair_page():
    """Simple pairing confirmation page for phone QR scan."""
    index_path = static_dir / "pair.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"success": True, "message": "Phone linked. You can now upload attendance photos."}


def main():
    import uvicorn

    config = load_config()
    uvicorn.run(
        "app.main:app",
        host=config["host"],
        port=int(config["port"]),
        reload=False,
    )


if __name__ == "__main__":
    main()