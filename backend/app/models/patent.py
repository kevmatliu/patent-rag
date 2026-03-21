from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel

from app.models.enums import ExtractionStatus


class Patent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_url: str = Field(index=True, unique=True)
    patent_slug: str = Field(index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    extraction_status: ExtractionStatus = Field(default=ExtractionStatus.PENDING)
    last_error: Optional[str] = Field(default=None)
