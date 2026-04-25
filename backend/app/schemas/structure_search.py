from __future__ import annotations

from typing import Dict, Optional
from pydantic import BaseModel, Field


class StructureSearchRequest(BaseModel):
    core_smiles: Optional[str] = None
    r_groups: Dict[str, str] = Field(default_factory=dict, description="Mapping of R-labels (e.g. R1) to SMILES")
    k: int = Field(default=20, ge=1, le=100)
