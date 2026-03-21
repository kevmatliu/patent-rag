from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel

from app.models.enums import ProcessingStatus


class CompoundImage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    patent_id: int = Field(foreign_key="patent.id", index=True)
    image_path: str
    page_number: Optional[int] = Field(default=None, index=True)
    processing_status: ProcessingStatus = Field(default=ProcessingStatus.PENDING, index=True)
    smiles: Optional[str] = Field(default=None)
    embedding: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_error: Optional[str] = Field(default=None)
