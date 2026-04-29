from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

class SaveCompoundRequest(BaseModel):
    smiles: str

class SaveCompoundResponse(BaseModel):
    compound_id: int


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
    is_duplicate_within_patent: bool = False
    duplicate_of_compound_id: Optional[int] = None
    kept_for_series_analysis: bool = False
    core_candidate_count: int = 0
    selected_core_candidate_id: Optional[int] = None
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


class CompoundSpaceNode(BaseModel):
    compound_id: int
    patent_id: int
    patent_code: str
    patent_source_url: str
    image_url: str
    page_number: Optional[int] = None
    smiles: Optional[str] = None
    canonical_smiles: Optional[str] = None
    has_embedding: bool
    x: float
    y: float
    cluster_id: int


class CompoundSpaceCluster(BaseModel):
    cluster_id: int
    x: float
    y: float
    member_count: int
    patent_counts: dict[str, int]


class CompoundSpaceResponse(BaseModel):
    nodes: list[CompoundSpaceNode]
    clusters: list[CompoundSpaceCluster]


class CompoundSelectionRequest(BaseModel):
    compound_ids: list[int] = Field(default_factory=list)


class PatentSelectionRequest(BaseModel):
    patent_ids: list[int] = Field(default_factory=list)


class CompoundSelectionResponse(BaseModel):
    affected_count: int


class CompoundCoreCandidateItem(BaseModel):
    id: int
    compound_id: int
    patent_id: int
    candidate_rank: int
    is_selected: bool
    core_smiles: Optional[str] = None
    core_smarts: Optional[str] = None
    reduced_core: Optional[str] = None
    murcko_scaffold_smiles: Optional[str] = None
    generation_method: Optional[str] = None
    pipeline_version: Optional[str] = None
    created_at: str
    updated_at: str


class CompoundDetailResponse(BaseModel):
    compound: CompoundBrowserItem
    core_candidates: list[CompoundCoreCandidateItem]


class CompoundCoreCandidateRGroupItem(BaseModel):
    core_candidate_id: int
    compound_id: int
    patent_id: int
    r_label: str
    r_group_smiles: str
    attachment_index: Optional[int] = None
    pipeline_version: Optional[str] = None
    created_at: str


class CompoundCoreCandidateRGroupResponse(BaseModel):
    compound_id: int
    core_candidate_id: int
    items: list[CompoundCoreCandidateRGroupItem]
