from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class SuccessResponse(BaseModel):
    success: bool
    message: Optional[str] = None