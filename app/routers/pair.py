from fastapi import APIRouter, Body

from app.schemas import PairDeviceOut, PairDeviceRequest

router = APIRouter(tags=["pair"])

@router.post("/pair", response_model=PairDeviceOut)
def pair_device(body: PairDeviceRequest | None = Body(default=None)):
    device = body.device_name if body else None
    return {
        "success": True,
        "message": "Phone linked successfully.",
        "device": device or "unknown",
    }