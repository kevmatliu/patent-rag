from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class PatentBatchRequest(BaseModel):
    urls: list[str] = Field(default_factory=list)


class PatentBatchItemResult(BaseModel):
    url: str
    patent_id: Optional[int] = None
    patent_code: Optional[str] = None
    extracted_images: int = 0
    extraction_status: str
    error: Optional[str] = None
    duplicate: bool = False


class PatentBatchResponse(BaseModel):
    results: list[PatentBatchItemResult]
