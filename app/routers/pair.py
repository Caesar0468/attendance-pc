from __future__ import annotations

from fastapi import APIRouter

# BUGFIX: this file used to expose GET /api/pair/info and POST /api/pair,
# both left over from before the mobile pairing-token system existed.
# GET /api/pair/info in particular built a pair_url with NO token at all
# ("http://{lan_ip}:{port}/pair.html", no ?token=...), which is exactly the
# bug that produces "No pairing token found in the link" on the phone.
# Nothing in the current frontend calls either endpoint — the real,
# token-carrying pairing URL is minted by GET /api/server-info in
# app/routers/system.py — but leaving the old ones registered on the API
# surface is a landmine: it's easy to accidentally wire a client back up to
# them and reintroduce the bug. Router kept (empty) so app/main.py's
# `app.include_router(pair.router)` doesn't need to change; add real
# endpoints here only if you have another client that specifically needs
# this prefix.
router = APIRouter(prefix="/api/pair", tags=["pair"])