"""Common/shared Pydantic schemas used across multiple domains"""

from pydantic import BaseModel

class SuccessResponse(BaseModel):
    """Generic success response"""

    success: bool

class MessageResponse(BaseModel):
    """Generic message response with success status"""

    success: bool
    message: str