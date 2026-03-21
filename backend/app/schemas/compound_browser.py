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
