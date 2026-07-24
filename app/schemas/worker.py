"""Pydantic schemas for worker-related requests and responses"""

from pydantic import BaseModel


class WorkerBase(BaseModel):
    id: int
    name: str
    thumbnail_path: str | None


class WorkerOut(WorkerBase):
    pass


class WorkerWithTimestamp(WorkerBase):
    created_at: str | None = None


class WorkerCreateOut(BaseModel):
    id: int
    name: str
    thumbnail_path: str | None


class WorkerListOut(BaseModel):
    workers: list[WorkerWithTimestamp]