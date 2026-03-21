from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.dependencies import get_health_service
from app.db.session import get_session
from app.schemas.health import HealthResponse
from app.services.health_service import HealthService


router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check(
    session: Session = Depends(get_session),
    health_service: HealthService = Depends(get_health_service),
) -> HealthResponse:
    return health_service.get_health(session)
