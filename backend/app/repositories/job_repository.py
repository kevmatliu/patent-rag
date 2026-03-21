from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlmodel import Session, select

from app.models.job_log import JobLog
from app.models.job_run import JobRun


class JobRepository:
    def create_job(self, session: Session, *, job_type: str) -> JobRun:
        job = JobRun(job_type=job_type)
        session.add(job)
        session.commit()
        session.refresh(job)
        return job

    def get_job(self, session: Session, job_id: str) -> Optional[JobRun]:
        statement = select(JobRun).where(JobRun.id == job_id)
        return session.exec(statement).first()

    def list_logs(self, session: Session, job_id: str) -> list[JobLog]:
        statement = select(JobLog).where(JobLog.job_id == job_id).order_by(JobLog.created_at, JobLog.id)
        return list(session.exec(statement).all())

    def start_job(self, session: Session, job: JobRun) -> JobRun:
        job.status = "running"
        job.cancel_requested = False
        job.started_at = datetime.now(timezone.utc)
        session.add(job)
        session.commit()
        session.refresh(job)
        return job

    def complete_job(self, session: Session, job: JobRun, *, summary: dict[str, Any]) -> JobRun:
        job.status = "completed"
        job.cancel_requested = False
        job.summary = json.dumps(summary)
        job.error = None
        job.finished_at = datetime.now(timezone.utc)
        session.add(job)
        session.commit()
        session.refresh(job)
        return job

    def fail_job(self, session: Session, job: JobRun, *, error: str, summary: Optional[dict[str, Any]] = None) -> JobRun:
        job.status = "failed"
        job.cancel_requested = False
        job.error = error
        job.summary = json.dumps(summary) if summary is not None else job.summary
        job.finished_at = datetime.now(timezone.utc)
        session.add(job)
        session.commit()
        session.refresh(job)
        return job

    def request_cancel(self, session: Session, job: JobRun) -> JobRun:
        job.cancel_requested = True
        if job.status in {"pending", "running"}:
            job.status = "cancelling"
        session.add(job)
        session.commit()
        session.refresh(job)
        return job

    def is_cancel_requested(self, session: Session, job_id: str) -> bool:
        job = self.get_job(session, job_id)
        if job is None:
            return False
        return bool(job.cancel_requested)

    def cancel_job(self, session: Session, job: JobRun, *, summary: Optional[dict[str, Any]] = None) -> JobRun:
        job.status = "cancelled"
        job.cancel_requested = False
        job.summary = json.dumps(summary) if summary is not None else job.summary
        job.error = None
        job.finished_at = datetime.now(timezone.utc)
        session.add(job)
        session.commit()
        session.refresh(job)
        return job

    def add_log(self, session: Session, *, job_id: str, message: str, level: str = "info") -> JobLog:
        log = JobLog(job_id=job_id, message=message, level=level)
        session.add(log)
        session.commit()
        session.refresh(log)
        return log
