# app/routers/attendance.py
from __future__ import annotations

import sqlite3
from fastapi import APIRouter, Cookie, Depends, HTTPException, WebSocket, WebSocketDisconnect

from app.database import get_connection, get_db
from app.dependencies import get_attendance_service
from app.repositories.attendance_repository import AttendanceRepository
from app.schemas import ConfirmUncertainOut, ConfirmUncertainRequest, TodayAttendanceOut
from app.schemas.attendance import AttendanceOverrideRequest, BulkOverrideRequest
from app.services.attendance_service import AttendanceService
from app.ws_manager import manager
from app.core.auth import get_current_user, require_manager_or_root

router = APIRouter(prefix="/api/today", tags=["today"])


@router.get("", response_model=TodayAttendanceOut)
def today_view(
    day: str | None = None,
    user: dict = Depends(get_current_user),
    service: AttendanceService = Depends(get_attendance_service),
):
    return service.get_today_attendance_summary(day)


@router.post("/confirm", response_model=ConfirmUncertainOut)
async def confirm_uncertain(
    body: ConfirmUncertainRequest,
    user: dict = Depends(get_current_user),
    service: AttendanceService = Depends(get_attendance_service),
):
    return await service.confirm_or_discard_uncertain_match(
        match_id=body.match_id, confirm=body.confirm, worker_id=body.worker_id,
    )


@router.put("/override")
def override_attendance(
    body: AttendanceOverrideRequest,
    user: dict = Depends(require_manager_or_root),
    service: AttendanceService = Depends(get_attendance_service),
):
    if body.session not in ("morning", "evening"):
        raise HTTPException(status_code=400, detail="Session must be 'morning' or 'evening'.")
    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="A reason is required for manual corrections.")
    service.attendance_repo.set_attendance_with_audit(
        worker_id=body.worker_id, date=body.date, session=body.session,
        new_value=body.present, changed_by=user["username"], reason=body.reason.strip(),
    )
    return {"success": True, "today": service.get_today_attendance_summary(body.date)}


@router.put("/override/bulk")
def override_attendance_bulk(
    body: BulkOverrideRequest,
    user: dict = Depends(require_manager_or_root),
    service: AttendanceService = Depends(get_attendance_service),
):
    from datetime import date as date_cls, timedelta

    if not body.reason.strip():
        raise HTTPException(status_code=400, detail="A reason is required for bulk corrections.")
    try:
        start = date_cls.fromisoformat(body.start_date)
        end = date_cls.fromisoformat(body.end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    if end < start:
        raise HTTPException(status_code=400, detail="End date must be on or after start date.")
    if (end - start).days > 62:
        raise HTTPException(status_code=400, detail="Range too large — please split into smaller batches (max ~2 months).")

    sessions = ("morning", "evening") if body.session == "both" else (body.session,)
    if any(s not in ("morning", "evening") for s in sessions):
        raise HTTPException(status_code=400, detail="Session must be 'morning', 'evening', or 'both'.")

    days_affected = 0
    cur = start
    while cur <= end:
        for s in sessions:
            service.attendance_repo.set_attendance_with_audit(
                worker_id=body.worker_id, date=cur.isoformat(), session=s,
                new_value=body.present, changed_by=user["username"], reason=body.reason.strip(),
            )
        days_affected += 1
        cur += timedelta(days=1)

    return {"success": True, "days_affected": days_affected}


@router.get("/audit/{worker_id}")
def get_audit_log(
    worker_id: int,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    rows = db.execute(
        "SELECT * FROM attendance_audit_log WHERE worker_id = ? ORDER BY changed_at DESC LIMIT 200",
        (worker_id,),
    ).fetchall()
    return {"entries": [dict(r) for r in rows]}


@router.websocket("/ws")
async def today_websocket(websocket: WebSocket, session_token: str | None = Cookie(default=None)):
    # BUGFIX: this endpoint had no auth check at all — any device on the LAN
    # could open it and get every attendance update (names, thumbnails)
    # streamed live. Browsers send cookies on the WS handshake for
    # same-origin connections, so we can check the same session cookie the
    # rest of the app uses, no separate token scheme needed.
    if not session_token:
        await websocket.close(code=4401)
        return

    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM sessions WHERE token = ? AND expires_at > datetime('now')",
            (session_token,),
        ).fetchone()
    if not row:
        await websocket.close(code=4401)
        return

    await manager.connect(websocket)
    try:
        with get_connection() as conn:
            repo = AttendanceRepository(conn)
            await websocket.send_json({"type": "attendance_update", "data": repo.get_today_attendance()})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)