from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select
from sqlmodel import Session

from app.core.config import get_settings
from app.core.dependencies import get_vector_index_service
from app.db.session import get_session
from app.models.compound_image import CompoundImage
from app.models.compound_r_group import CompoundRGroup
from app.models.job_log import JobLog
from app.models.job_run import JobRun
from app.models.patent import Patent
from app.schemas.admin import ResetDatabaseResponse
from app.services.vector_index_service import VectorIndexService


router = APIRouter(prefix="/api/admin", tags=["admin"])


def _scalar_count(session: Session, statement) -> int:
    value = session.exec(statement).one()
    if not isinstance(value, (int, float)) and hasattr(value, "__getitem__"):
        return int(value[0] or 0)
    return int(value or 0)


def _clear_directory(root: Path) -> int:
    if not root.exists():
        return 0
    deleted = 0
    for child in root.rglob("*"):
        if child.is_file() or child.is_symlink():
            child.unlink()
            deleted += 1
    for child in sorted(root.rglob("*"), reverse=True):
        if child.is_dir():
            child.rmdir()
    root.mkdir(parents=True, exist_ok=True)
    return deleted


@router.post("/reset-database", response_model=ResetDatabaseResponse)
def reset_database(
    session: Session = Depends(get_session),
    vector_index_service: VectorIndexService = Depends(get_vector_index_service),
) -> ResetDatabaseResponse:
    settings = get_settings()

    compound_count = _scalar_count(session, select(func.count()).select_from(CompoundImage))
    r_group_count = _scalar_count(session, select(func.count()).select_from(CompoundRGroup))
    patent_count = _scalar_count(session, select(func.count()).select_from(Patent))
    job_count = _scalar_count(session, select(func.count()).select_from(JobRun))
    log_count = _scalar_count(session, select(func.count()).select_from(JobLog))

    session.exec(delete(JobLog))
    session.exec(delete(JobRun))
    session.exec(delete(CompoundRGroup))
    session.exec(delete(CompoundImage))
    session.exec(delete(Patent))
    session.commit()

    vector_index_service.rebuild([])

    files_deleted = 0
    files_deleted += _clear_directory(settings.extracted_image_dir)
    files_deleted += _clear_directory(settings.search_tmp_dir)

    return ResetDatabaseResponse(
        patents_deleted=patent_count,
        compounds_deleted=compound_count,
        jobs_deleted=job_count,
        logs_deleted=log_count,
        files_deleted=files_deleted,
    )
