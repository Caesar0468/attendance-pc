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


class ShutdownOut(BaseModel):
    success: bool
    message: str


class PairDeviceRequest(BaseModel):
    device_name: Optional[str] = None


class PairDeviceOut(BaseModel):
    success: bool
    message: str