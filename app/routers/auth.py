# app/routers/auth.py
from __future__ import annotations

import sqlite3
import secrets
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel
from app.database import get_db
from app.core.auth import verify_password, get_current_user, get_password_hash, require_root

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class SetupRequest(BaseModel):
    username: str
    password: str


class CreateUserRequest(BaseModel):
    username: str
    password: str


@router.get("/setup-status")
def setup_status(db: sqlite3.Connection = Depends(get_db)):
    count = db.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    return {"needs_setup": count == 0}


@router.post("/setup")
def setup_root(req: SetupRequest, db: sqlite3.Connection = Depends(get_db)):
    if db.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] > 0:
        raise HTTPException(status_code=409, detail="Setup already completed.")
    clean_user = req.username.strip()
    if not clean_user:
        raise HTTPException(status_code=400, detail="Username cannot be empty.")
    if len(req.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters.")
    db.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'root')",
        (clean_user, get_password_hash(req.password)),
    )
    return {"success": True}


@router.post("/login")
def login(req: LoginRequest, response: Response, db: sqlite3.Connection = Depends(get_db)):
    user = db.execute("SELECT * FROM users WHERE username = ?", (req.username,)).fetchone()
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, datetime('now', '+30 days'))",
        (token, user["id"]),
    )
    response.set_cookie(
        key="session_token", value=token, httponly=True, samesite="lax", max_age=30 * 24 * 3600,
    )
    return {"success": True, "username": user["username"], "role": user["role"]}


@router.post("/logout")
def logout(
    response: Response,
    session_token: str | None = Cookie(default=None),
    db: sqlite3.Connection = Depends(get_db),
):
    if session_token:
        db.execute("DELETE FROM sessions WHERE token = ?", (session_token,))
    response.delete_cookie("session_token")
    return {"success": True}


@router.get("/me")
def get_me(user: dict = Depends(get_current_user)):
    return {"logged_in": True, "user": user}


# --- USER MANAGEMENT (root only) ---

@router.get("/users")
def list_users(user: dict = Depends(require_root), db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute("SELECT id, username, role, created_at FROM users ORDER BY id").fetchall()
    return {"users": [dict(r) for r in rows]}


@router.post("/users")
def create_manager(req: CreateUserRequest, user: dict = Depends(require_root), db: sqlite3.Connection = Depends(get_db)):
    clean_user = req.username.strip()
    if not clean_user:
        raise HTTPException(status_code=400, detail="Username cannot be empty.")
    if db.execute("SELECT 1 FROM users WHERE username=?", (clean_user,)).fetchone():
        raise HTTPException(status_code=409, detail="Username already taken.")
    if len(req.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters.")
    cur = db.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'manager')",
        (clean_user, get_password_hash(req.password)),
    )
    return {"success": True, "id": cur.lastrowid}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, user: dict = Depends(require_root), db: sqlite3.Connection = Depends(get_db)):
    if user_id == user["id"]:
        raise HTTPException(status_code=400, detail="You can't remove your own account.")
    target = db.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    if target["role"] == "root" and db.execute("SELECT COUNT(*) c FROM users WHERE role='root'").fetchone()["c"] <= 1:
        raise HTTPException(status_code=400, detail="Can't remove the last root account.")
    db.execute("DELETE FROM users WHERE id=?", (user_id,))
    db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    return {"success": True}