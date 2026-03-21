from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class JobAcceptedResponse(BaseModel):
    job_id: str
    status: str


class JobLogItem(BaseModel):
    id: int
    level: str
    message: str
    created_at: str


class JobStatusResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    cancel_requested: bool = False
    error: Optional[str] = None
    logs: list[JobLogItem]
    summary: Optional[dict[str, Any]] = None
