from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class CompoundBrowserItem(BaseModel):
    compound_id: int
    patent_id: int
    patent_code: str
    patent_source_url: str
    image_url: str
    page_number: Optional[int] = None
    processing_status: str
    smiles: Optional[str] = None
    canonical_smiles: Optional[str] = None
    validation_status: Optional[str] = None
    is_compound: Optional[bool] = None
    is_duplicate_within_patent: bool = False
    duplicate_of_compound_id: Optional[int] = None
    kept_for_series_analysis: bool = False
    murcko_scaffold_smiles: Optional[str] = None
    reduced_core: Optional[str] = None
    core_smiles: Optional[str] = None
    core_smarts: Optional[str] = None
    validation_error: Optional[str] = None
    pipeline_version: Optional[str] = None
    has_embedding: bool
    created_at: str
    updated_at: str
    last_error: Optional[str] = None


class CompoundBrowserResponse(BaseModel):
    items: list[CompoundBrowserItem]
    total: int
    offset: int
    limit: int


class CompoundSelectionRequest(BaseModel):
    compound_ids: list[int] = Field(default_factory=list)


class CompoundSelectionResponse(BaseModel):
    affected_count: int


class CompoundRGroupItem(BaseModel):
    compound_id: int
    patent_id: int
    core_smiles: Optional[str] = None
    core_smarts: Optional[str] = None
    r_label: str
    r_group: str
    pipeline_version: Optional[str] = None
    created_at: str


class CompoundRGroupResponse(BaseModel):
    compound_id: int
    items: list[CompoundRGroupItem]
