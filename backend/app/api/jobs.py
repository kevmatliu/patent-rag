from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db.session import get_session
from app.repositories.job_repository import JobRepository
from app.schemas.job import JobAcceptedResponse, JobLogItem, JobStatusResponse


router = APIRouter(prefix="/api/jobs", tags=["jobs"])

job_repository = JobRepository()


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str, session: Session = Depends(get_session)) -> JobStatusResponse:
    job = job_repository.get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    logs = job_repository.list_logs(session, job_id)
    summary = json.loads(job.summary) if job.summary else None

    return JobStatusResponse(
        job_id=job.id,
        job_type=job.job_type,
        status=job.status,
        cancel_requested=job.cancel_requested,
        error=job.error,
        logs=[
            JobLogItem(
                id=log.id or 0,
                level=log.level,
                message=log.message,
                created_at=log.created_at.isoformat(),
            )
            for log in logs
        ],
        summary=summary,
    )


@router.post("/{job_id}/cancel", response_model=JobAcceptedResponse)
def cancel_job(job_id: str, session: Session = Depends(get_session)) -> JobAcceptedResponse:
    job = job_repository.get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status in {"completed", "failed", "cancelled"}:
        return JobAcceptedResponse(job_id=job.id, status=job.status)

    job_repository.request_cancel(session, job)
    job_repository.add_log(session, job_id=job.id, level="info", message="Stop requested by user.")
    return JobAcceptedResponse(job_id=job.id, status="cancelling")
