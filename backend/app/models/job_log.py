from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class JobLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: str = Field(foreign_key="jobrun.id", index=True)
    level: str = Field(default="info")
    message: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
