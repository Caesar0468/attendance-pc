import json
import socket
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"

DATA_DIR = BASE_DIR / "data"
PHOTOS_DIR = BASE_DIR / "photos"
UPLOADS_DIR = BASE_DIR / "uploads"
REPORTS_DIR = BASE_DIR / "reports"
DB_PATH = DATA_DIR / "attendance.db"

DEFAULT_CONFIG = {
    "port": 8500,
    "host": "0.0.0.0",
    "similarity_threshold": 0.5,
    "uncertain_threshold": 0.35,
    "photos_per_worker_min": 2,
    "photos_per_worker_max": 3,
}

def load_config() -> dict:
    """Load config.json, falling back to defaults for any missing keys."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        merged = {**DEFAULT_CONFIG, **data}
        return merged
    return DEFAULT_CONFIG.copy()

def save_config(updates: dict) -> dict:
    """Merge updates into the existing config and persist to disk."""
    config = load_config()
    config.update(updates)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    return config

def ensure_dirs() -> None:
    """Create all runtime data directories if they don't already exist."""
    for path in (DATA_DIR, PHOTOS_DIR, UPLOADS_DIR, REPORTS_DIR):
        path.mkdir(parents=True, exist_ok=True)

def get_local_ip() -> str:
    """Get the local IP address of the machine on the network."""
    try:
        # Create a dummy socket connection to determine the local routing IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        # Fallback if there is no active network connection
        return "127.0.0.1"