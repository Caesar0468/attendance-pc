"""Pydantic schemas for system, pairing, and health check requests and responses"""

from pydantic import BaseModel

class HealthOut(BaseModel):
    """Health check response"""

    status: str

class ServerInfoOut(BaseModel):
    """Server information response with network details"""

    local_ip: str
    port: int
    pair_url: str
    app_url: str

class PairDeviceRequest(BaseModel):
    """Request to pair a device"""

    device_name: str | None = None

class PairDeviceOut(BaseModel):
    """Response after pairing a device"""

    success: bool
    message: str
    device: str

class ShutdownOut(BaseModel):
    """Response after shutdown request"""

    success: bool
    message: str