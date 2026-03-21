from __future__ import annotations

from pathlib import Path
from typing import Optional

import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.dependencies import get_processing_service, get_vector_index_service
from app.db.session import get_session
from app.models.compound_image import CompoundImage
from app.repositories.compound_image_repository import CompoundImageRepository
from app.repositories.job_repository import JobRepository
from app.repositories.patent_repository import PatentRepository
from app.schemas.compound_browser import (
    CompoundBrowserItem,
    CompoundBrowserResponse,
    CompoundSelectionRequest,
    CompoundSelectionResponse,
)
from app.schemas.job import JobAcceptedResponse
from app.schemas.image_processing import ProcessFailure
from app.services.processing_service import ProcessingService


router = APIRouter(prefix="/api/compounds", tags=["compounds"])

compound_repository = CompoundImageRepository()
patent_repository = PatentRepository()
job_repository = JobRepository()


@router.get("", response_model=CompoundBrowserResponse)
def browse_compounds(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=24, ge=1, le=100),
    patent_code: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
) -> CompoundBrowserResponse:
    settings = get_settings()
    rows, total = compound_repository.list_browser_rows(
        session,
        offset=offset,
        limit=limit,
        patent_code=patent_code.strip() if patent_code else None,
    )

    items = []
    upload_root = settings.upload_dir.resolve()
    for compound_row, patent_row in rows:
        image_path = Path(compound_row.image_path).resolve()
        relative_image = image_path.relative_to(upload_root)
        items.append(
            CompoundBrowserItem(
                compound_id=compound_row.id or 0,
                patent_id=patent_row.id or 0,
                patent_code=patent_row.patent_slug,
                patent_source_url=patent_row.source_url,
                image_url=f"/static/{relative_image.as_posix()}",
                page_number=compound_row.page_number,
                processing_status=compound_row.processing_status.value,
                smiles=compound_row.smiles,
                has_embedding=compound_row.embedding is not None,
                created_at=compound_row.created_at.isoformat(),
                updated_at=compound_row.updated_at.isoformat(),
                last_error=compound_row.last_error,
            )
        )

    return CompoundBrowserResponse(items=items, total=total, offset=offset, limit=limit)


def _rebuild_index(session: Session) -> None:
    vector_index = get_vector_index_service()
    items = []
    for image in compound_repository.list_indexable(session):
        if image.id is None or image.embedding is None:
            continue
        items.append((image.id, json.loads(image.embedding)))
    vector_index.rebuild(items)


def _run_selected_processing_job(
    job_id: str,
    limit: int,
    processing_service: ProcessingService,
) -> None:
    from app.db.session import engine

    with Session(engine) as session:
        job = job_repository.get_job(session, job_id)
        if job is None:
            return

        job_repository.start_job(session, job)
        def log_progress(level: str, message: str) -> None:
            job_repository.add_log(session, job_id=job_id, level=level, message=message)

        summary_raw = json.loads(job.summary) if job.summary else {}
        result = processing_service.process_images(
            session,
            limit=limit,
            order="oldest",
            compound_ids=summary_raw.get("compound_ids") or [],
            progress_callback=log_progress,
            should_stop=lambda: job_repository.is_cancel_requested(session, job_id),
        )
        summary = {
            "processed_count": len(result.processed_image_ids),
            "failed_count": len(result.failures),
            "processed_image_ids": result.processed_image_ids,
            "failures": [
                ProcessFailure(image_id=item.image_id, error=item.error).model_dump()
                for item in result.failures
            ],
            "stopped_early": result.stopped_early,
        }
        if result.stopped_early:
            job_repository.cancel_job(session, job, summary=summary)
        else:
            job_repository.complete_job(session, job, summary=summary)


@router.post("/delete", response_model=CompoundSelectionResponse)
def delete_compounds(
    payload: CompoundSelectionRequest,
    session: Session = Depends(get_session),
) -> CompoundSelectionResponse:
    deleted = compound_repository.delete_by_ids(session, compound_ids=payload.compound_ids)
    _rebuild_index(session)
    return CompoundSelectionResponse(affected_count=deleted)


@router.post("/reprocess", response_model=JobAcceptedResponse)
def reprocess_compounds(
    payload: CompoundSelectionRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    processing_service: ProcessingService = Depends(get_processing_service),
) -> JobAcceptedResponse:
    reset_count = compound_repository.reset_for_reprocess(session, compound_ids=payload.compound_ids)
    _rebuild_index(session)
    job = job_repository.create_job(session, job_type="image_processing")
    job.summary = json.dumps({"compound_ids": payload.compound_ids})
    session.add(job)
    session.commit()
    session.refresh(job)
    job_repository.add_log(session, job_id=job.id, message=f"Queued {reset_count} compound(s) for reprocessing.")
    background_tasks.add_task(_run_selected_processing_job, job.id, reset_count, processing_service)
    return JobAcceptedResponse(job_id=job.id, status=job.status)


@router.delete("/patent/{patent_code}", response_model=CompoundSelectionResponse)
def delete_patent(
    patent_code: str,
    session: Session = Depends(get_session),
) -> CompoundSelectionResponse:
    patent = patent_repository.get_by_slug(session, patent_code)
    if patent is None:
        raise HTTPException(status_code=404, detail="Patent not found")
    compound_ids = [item.id for item in session.exec(select(CompoundImage).where(CompoundImage.patent_id == patent.id)).all() if item.id]
    deleted = compound_repository.delete_by_ids(session, compound_ids=compound_ids)
    patent_repository.delete(session, patent)
    _rebuild_index(session)
    return CompoundSelectionResponse(affected_count=deleted)
