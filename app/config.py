# app/config.py
import json
import logging
import socket
from pathlib import Path

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"

DATA_DIR = BASE_DIR / "data"
PHOTOS_DIR = BASE_DIR / "photos"
UPLOADS_DIR = BASE_DIR / "uploads"
THUMBNAILS_DIR = UPLOADS_DIR / "thumbnails"
CROPS_DIR = UPLOADS_DIR / "crops"
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

_CONFIG_TYPES = {
    "port": int,
    "host": str,
    "similarity_threshold": float,
    "uncertain_threshold": float,
    "photos_per_worker_min": int,
    "photos_per_worker_max": int,
}


def _validate_config(data: dict) -> dict:
    clean = dict(data)
    for key, expected_type in _CONFIG_TYPES.items():
        if key not in clean:
            continue
        value = clean[key]
        if isinstance(value, bool) or not isinstance(value, expected_type):
            logger.warning(
                "config.json: %r has invalid type %r (expected %s); using default",
                key, type(value).__name__, expected_type.__name__,
            )
            clean[key] = DEFAULT_CONFIG[key]

    if clean.get("photos_per_worker_min", 0) > clean.get("photos_per_worker_max", 0):
        logger.warning(
            "photos_per_worker_min > photos_per_worker_max in config.json; using defaults"
        )
        clean["photos_per_worker_min"] = DEFAULT_CONFIG["photos_per_worker_min"]
        clean["photos_per_worker_max"] = DEFAULT_CONFIG["photos_per_worker_max"]

    if clean.get("uncertain_threshold", 0) > clean.get("similarity_threshold", 0):
        logger.warning(
            "uncertain_threshold > similarity_threshold in config.json; using defaults"
        )
        clean["uncertain_threshold"] = DEFAULT_CONFIG["uncertain_threshold"]
        clean["similarity_threshold"] = DEFAULT_CONFIG["similarity_threshold"]

    return clean


def load_config() -> dict:
    """Load config.json, falling back to defaults for missing or invalid keys."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("config.json must contain a JSON object")
        except (json.JSONDecodeError, ValueError, OSError) as e:
            logger.error("Failed to load %s (%s); falling back to defaults", CONFIG_PATH, e)
            return DEFAULT_CONFIG.copy()

        merged = {**DEFAULT_CONFIG, **data}
        return _validate_config(merged)
    return DEFAULT_CONFIG.copy()


def save_config(updates: dict) -> dict:
    """Merge updates into the existing config and persist to disk."""
    config = load_config()
    config.update(updates)
    config = _validate_config(config)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    return config


def ensure_dirs() -> None:
    """Create all runtime data directories if they don't already exist."""
    for path in (DATA_DIR, PHOTOS_DIR, UPLOADS_DIR, THUMBNAILS_DIR, CROPS_DIR, REPORTS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def get_local_ip() -> str:
    """Get local LAN IP address."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"