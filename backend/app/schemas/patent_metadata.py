from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class PatentMetadataItem(BaseModel):
    patent_id: int
    patent_code: str
    source_url: str
    extraction_status: str
    total_compounds: int
    processed_compounds: int
    unprocessed_compounds: int
    failed_compounds: int
    created_at: str
    last_error: Optional[str] = None


class PatentMetadataSummary(BaseModel):
    total_patents: int
    processed_patents: int
    unprocessed_patents: int


class PatentMetadataResponse(BaseModel):
    items: list[PatentMetadataItem]
    summary: PatentMetadataSummary
    total: int
    offset: int
    limit: int
