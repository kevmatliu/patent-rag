from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class ComponentHealth(BaseModel):
    status: str
    detail: str
    meta: Optional[dict[str, Any]] = None


class HealthResponse(BaseModel):
    status: str
    components: dict[str, ComponentHealth]
