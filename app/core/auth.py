# app/core/auth.py
from __future__ import annotations

import secrets
import sqlite3
import bcrypt
from fastapi import Cookie, Depends, Header, HTTPException
from app.database import get_db


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain text password against the stored bcrypt hash."""
    try:
        # Truncate the same way get_password_hash does before hashing, so a
        # very long password can't cause bcrypt to raise here (which used to
        # surface as a mysterious silent login failure for long passwords
        # instead of a normal "invalid password").
        pwd_bytes = plain_password.encode("utf-8")[:72]
        return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Hashes a password using native bcrypt."""
    # Truncate to 72 bytes to respect bcrypt's standard limit
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def get_current_user(
    session_token: str | None = Cookie(default=None),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    if not session_token:
        raise HTTPException(status_code=401, detail="Not logged in.")

    row = db.execute(
        """
        SELECT u.id, u.username, u.role 
        FROM sessions s 
        JOIN users u ON s.user_id = u.id 
        WHERE s.token = ? AND s.expires_at > datetime('now')
        """,
        (session_token,),
    ).fetchone()

    if not row:
        raise HTTPException(status_code=401, detail="Session expired or invalid.")

    return dict(row)


def require_role(*roles: str):
    def dependency(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="You don't have permission to do that.")
        return user
    return dependency


require_root = require_role("root")
require_manager_or_root = require_role("root", "manager")
require_any_user = get_current_user  # alias for read-only routes — any logged-in role


# --- MOBILE PAIRING TOKENS -------------------------------------------------
# BUGFIX: worker enrollment (POST /api/workers) and photo upload
# (POST /api/upload-photo) used to have NO auth dependency at all, so any
# device on the LAN could enroll/overwrite a worker's face embeddings or
# flood in fake attendance photos, no login required. Those two endpoints
# are used by the unauthenticated field/mobile flow (pair.html), which by
# design has no login screen of its own — supervisors just scan a QR code.
# Instead of requiring a full login there (which would break that flow),
# we gate them behind a short-lived pairing token that is only ever handed
# out to an already-logged-in root/manager via the "Pair Mobile" QR modal.

def issue_pair_token(db: sqlite3.Connection, created_by: str, hours: int = 12) -> str:
    """Mints a new pairing token, embedded in the QR/pair URL. Also sweeps
    expired tokens so this table doesn't grow forever."""
    db.execute("DELETE FROM pair_tokens WHERE expires_at <= datetime('now')")
    token = secrets.token_urlsafe(24)
    db.execute(
        "INSERT INTO pair_tokens (token, created_by, expires_at) VALUES (?, ?, datetime('now', ?))",
        (token, created_by, f"+{hours} hours"),
    )
    return token


def _verify_pair_token(db: sqlite3.Connection, token: str) -> bool:
    row = db.execute(
        "SELECT 1 FROM pair_tokens WHERE token = ? AND expires_at > datetime('now')",
        (token,),
    ).fetchone()
    return row is not None


def require_pairing_or_user(
    session_token: str | None = Cookie(default=None),
    x_pair_token: str | None = Header(default=None, alias="X-Pair-Token"),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Allows either a normal logged-in dashboard session OR a valid
    short-lived mobile pairing token. Used only on the two endpoints the
    unauthenticated field/mobile flow needs to call."""
    if session_token:
        row = db.execute(
            """
            SELECT u.id, u.username, u.role
            FROM sessions s JOIN users u ON s.user_id = u.id
            WHERE s.token = ? AND s.expires_at > datetime('now')
            """,
            (session_token,),
        ).fetchone()
        if row:
            return dict(row)

    if x_pair_token and _verify_pair_token(db, x_pair_token):
        return {"id": None, "username": "mobile-field-device", "role": "field"}

    raise HTTPException(
        status_code=401,
        detail="Not logged in, and no valid pairing token. Re-scan the QR code from the dashboard.",
    )