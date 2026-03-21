from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlmodel import Session

from app.core.dependencies import get_processing_service
from app.db.session import engine, get_session
from app.repositories.job_repository import JobRepository
from app.repositories.compound_image_repository import CompoundImageRepository
from app.schemas.job import JobAcceptedResponse
from app.schemas.image_processing import (
    ProcessFailure,
    ProcessImagesRequest,
    UnprocessedCountResponse,
)
from app.services.processing_service import ProcessingService


router = APIRouter(prefix="/api/images", tags=["images"])

compound_repository = CompoundImageRepository()
job_repository = JobRepository()

def _run_processing_job(job_id: str, limit: int, order: str, processing_service: ProcessingService) -> None:
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
            order=order,
            patent_codes=summary_raw.get("patent_codes") or [],
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


@router.post("/process", response_model=JobAcceptedResponse)
def process_images(
    payload: ProcessImagesRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    processing_service: ProcessingService = Depends(get_processing_service),
) -> JobAcceptedResponse:
    job = job_repository.create_job(session, job_type="image_processing")
    job.summary = json.dumps(
        {
            "patent_codes": payload.patent_codes,
            "compound_ids": payload.compound_ids,
        }
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    background_tasks.add_task(_run_processing_job, job.id, payload.limit, payload.order, processing_service)
    return JobAcceptedResponse(job_id=job.id, status=job.status)


@router.get("/unprocessed-count", response_model=UnprocessedCountResponse)
def get_unprocessed_count(session: Session = Depends(get_session)) -> UnprocessedCountResponse:
    return UnprocessedCountResponse(count=compound_repository.count_unprocessed(session))
