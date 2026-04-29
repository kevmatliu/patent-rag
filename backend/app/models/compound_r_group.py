from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class CompoundRGroup(SQLModel, table=True):
    __tablename__ = "compound_r_group"
    # Deprecated legacy table retained only so historical rows can be migrated
    # into CompoundCoreCandidateRGroup and downgraded if needed.

    id: Optional[int] = Field(default=None, primary_key=True)
    compound_id: int = Field(foreign_key="compoundimage.id", index=True)
    patent_id: int = Field(index=True)
    core_smiles: Optional[str] = Field(default=None)
    core_smarts: Optional[str] = Field(default=None)
    r_label: str = Field(index=True)
    r_group: str
    pipeline_version: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
