"""Custom exceptions for the application."""

from typing import Any
from fastapi import HTTPException, status

class BaseAppException(HTTPException):
    """Base custom exception for consistent error handling."""
    def __init__(self, status_code: int, detail: Any = None):
        super().__init__(status_code=status_code, detail=detail)

class InvalidInputException(BaseAppException):
    """Raised for invalid user input (e.g., malformed dates, empty fields)."""
    def __init__(self, detail: str = "Invalid input provided."):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

class NotFoundException(BaseAppException):
    """Raised when a requested resource is not found."""
    def __init__(self, detail: str = "Resource not found."):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

class FaceDetectionError(BaseAppException):
    """Raised when face detection or embedding extraction fails."""
    def __init__(self, detail: str = "Could not detect faces or extract embeddings from the photo."):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

class WorkerNotFoundError(NotFoundException):
    """Raised when a worker cannot be found."""
    def __init__(self, detail: str = "Worker not found."):
        super().__init__(detail=detail)

class UncertainMatchNotFoundError(NotFoundException):
    """Raised when an uncertain match record is not found."""
    def __init__(self, detail: str = "That item is no longer pending or does not exist."):
        super().__init__(detail=detail)

class FileProcessingError(BaseAppException):
    """Raised when there's an issue processing an uploaded file."""
    def __init__(self, detail: str = "Could not process the uploaded file."):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

class DuplicateWorkerError(BaseAppException):
    """Raised when attempting to create a worker with a name that already exists."""
    def __init__(self, detail: str = "Worker with this name already exists."):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)

class ConfigurationError(BaseAppException):
    """Raised when there's an issue with application configuration."""
    def __init__(self, detail: str = "Application configuration error."):
        super().__init__(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)