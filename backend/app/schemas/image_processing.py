from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ProcessImagesRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=1000)
    order: Literal["oldest", "newest"] = "oldest"
    patent_codes: list[str] = Field(default_factory=list)
    compound_ids: list[int] = Field(default_factory=list)


class ProcessFailure(BaseModel):
    image_id: int
    error: str


class ProcessImagesResponse(BaseModel):
    processed_count: int
    failed_count: int
    processed_image_ids: list[int]
    failures: list[ProcessFailure]
    stopped_early: bool = False


class UnprocessedCountResponse(BaseModel):
    count: int


class SearchResultItem(BaseModel):
    image_id: int
    similarity: float
    smiles: Optional[str] = None
    image_url: str
    patent_code: str
    page_number: Optional[int] = None
    patent_source_url: str


class SearchResponse(BaseModel):
    query_smiles: str
    results: list[SearchResultItem]
