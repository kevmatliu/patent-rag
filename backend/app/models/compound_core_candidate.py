from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


class CompoundCoreCandidate(SQLModel, table=True):
    __tablename__ = "compound_core_candidate"

    id: Optional[int] = Field(default=None, primary_key=True)
    compound_id: int = Field(foreign_key="compoundimage.id", index=True)
    patent_id: int = Field(foreign_key="patent.id", index=True)
    candidate_rank: int = Field(default=1, index=True)
    is_selected: bool = Field(default=False, index=True)
    core_smiles: Optional[str] = Field(default=None, index=True)
    core_smarts: Optional[str] = Field(default=None)
    reduced_core: Optional[str] = Field(default=None)
    murcko_scaffold_smiles: Optional[str] = Field(default=None, index=True)
    generation_method: Optional[str] = Field(default=None)
    pipeline_version: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    compound: Optional["CompoundImage"] = Relationship(back_populates="core_candidates")
    r_groups: list["CompoundCoreCandidateRGroup"] = Relationship(back_populates="core_candidate")
