from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import ProcessingStatus, ValidationStatus


class CompoundImage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    patent_id: int = Field(foreign_key="patent.id", index=True)
    image_path: str
    page_number: Optional[int] = Field(default=None, index=True)
    processing_status: ProcessingStatus = Field(default=ProcessingStatus.PENDING, index=True)
    smiles: Optional[str] = Field(default=None)
    canonical_smiles: Optional[str] = Field(default=None)
    embedding: Optional[str] = Field(default=None)
    is_compound: Optional[bool] = Field(default=None, index=True)
    validation_status: ValidationStatus = Field(default=ValidationStatus.UNPROCESSED, index=True)
    validation_error: Optional[str] = Field(default=None)
    is_duplicate_within_patent: bool = Field(default=False, index=True)
    duplicate_of_compound_id: Optional[int] = Field(default=None, index=True)
    kept_for_series_analysis: bool = Field(default=False, index=True)
    pipeline_version: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_error: Optional[str] = Field(default=None)
    core_candidates: list["CompoundCoreCandidate"] = Relationship(back_populates="compound")
