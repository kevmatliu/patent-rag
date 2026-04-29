from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


class CompoundCoreCandidateRGroup(SQLModel, table=True):
    __tablename__ = "compound_core_candidate_r_group"

    id: Optional[int] = Field(default=None, primary_key=True)
    core_candidate_id: int = Field(foreign_key="compound_core_candidate.id", index=True)
    compound_id: int = Field(foreign_key="compoundimage.id", index=True)
    patent_id: int = Field(foreign_key="patent.id", index=True)
    r_label: str = Field(index=True)
    r_group_smiles: str
    attachment_index: Optional[int] = Field(default=None, index=True)
    pipeline_version: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    core_candidate: Optional["CompoundCoreCandidate"] = Relationship(back_populates="r_groups")
