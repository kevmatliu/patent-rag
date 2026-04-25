from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SimilarCoreRecommendationRequest(BaseModel):
    core_smiles: str = Field(min_length=1)
    k: int = Field(default=20, ge=1, le=100)


class SimilarCoreRecommendationItem(BaseModel):
    core_smiles: str
    apply_core_smiles: str
    score: float
    support_count: int
    reason: str


class RGroupRecommendationRequest(BaseModel):
    core_smiles: str = Field(min_length=1)
    attachment_point: str = Field(min_length=1)
    k: int = Field(default=20, ge=1, le=100)


class RGroupRecommendationItem(BaseModel):
    rgroup_smiles: str
    count: int
    reason: str


class ApplyModificationRequest(BaseModel):
    current_smiles: str = Field(min_length=1)
    target_core_smiles: Optional[str] = None
    attachment_point: Optional[str] = None
    rgroup_smiles: Optional[str] = None


class ApplyModificationResponse(BaseModel):
    smiles: str
    core_smiles: str


class DecomposeStructureRequest(BaseModel):
    current_smiles: str = Field(min_length=1)


class DecomposedStructureRGroupItem(BaseModel):
    r_label: str
    r_group: str


class DecomposeStructureResponse(BaseModel):
    canonical_smiles: str
    reduced_core: str
    labeled_core_smiles: str
    attachment_points: list[str]
    r_groups: list[DecomposedStructureRGroupItem]
