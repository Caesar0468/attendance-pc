"""Pydantic schemas for worker-related requests and responses"""

from pydantic import BaseModel

class WorkerBase(BaseModel):
    """Base worker fields shared across responses"""

    id: int
    name: str
    thumbnail_path: str | None

class WorkerOut(WorkerBase):
    """Single worker output"""

    pass

class WorkerWithTimestamp(WorkerBase):
    """Worker with creation timestamp"""

    created_at: str

class WorkerCreateOut(BaseModel):
    """Worker creation/update output (without created_at)"""

    id: int
    name: str
    thumbnail_path: str | None

class WorkerListOut(BaseModel):
    """List of workers response"""

    workers: list[WorkerWithTimestamp]