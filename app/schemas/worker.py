from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel


class WorkerBase(BaseModel):
    id: int
    name: str
    thumbnail_path: Optional[str] = None


class WorkerOut(WorkerBase):
    pass


class WorkerWithTimestamp(WorkerBase):
    created_at: Optional[str] = None


class WorkerCreateOut(BaseModel):
    id: int
    name: str
    thumbnail_path: Optional[str] = None


class WorkerListOut(BaseModel):
    workers: List[WorkerWithTimestamp]