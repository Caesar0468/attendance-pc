from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class HealthOut(BaseModel):
    status: str


class ServerInfoOut(BaseModel):
    local_ip: str
    port: int
    pair_url: str
    app_url: str
    # BUGFIX: /server-info and /qr-code used to each mint their own pairing
    # token independently, so the URL text shown to the user and the QR
    # code image scanned by the phone carried two DIFFERENT tokens. This
    # field lets the frontend pass the already-minted token straight to
    # /qr-code so both always agree.
    pair_token: str


class ShutdownOut(BaseModel):
    success: bool
    message: str


class PairDeviceRequest(BaseModel):
    device_name: Optional[str] = None


class PairDeviceOut(BaseModel):
    success: bool
    message: str