from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from sqlmodel import Session

from app.core.config import get_settings
from app.db.session import engine
from app.core.dependencies import get_search_service
from app.db.session import get_session
from app.repositories.job_repository import JobRepository
from app.schemas.job import JobAcceptedResponse
from app.schemas.image_processing import SearchResponse
from app.schemas.structure_search import StructureSearchRequest
from app.services.search_service import SearchService


router = APIRouter(prefix="/api/search", tags=["search"])
job_repository = JobRepository()


def _run_search_job(job_id: str, file_path: str, k: int, patent_codes: list[str], search_service: SearchService) -> None:
    with Session(engine) as session:
        job = job_repository.get_job(session, job_id)
        if job is None:
            Path(file_path).unlink(missing_ok=True)
            return

        job_repository.start_job(session, job)

        def log_progress(level: str, message: str) -> None:
            job_repository.add_log(session, job_id=job_id, level=level, message=message)

        try:
            result = search_service.search_by_image_path(
                session,
                image_path=Path(file_path),
                k=k,
                patent_codes=patent_codes,
                progress_callback=log_progress,
            )
            job_repository.complete_job(session, job, summary=result.model_dump())
        except Exception as exc:
            job_repository.add_log(session, job_id=job_id, level="error", message=f"Search failed: {exc}")
            job_repository.fail_job(session, job, error=str(exc))
        finally:
            Path(file_path).unlink(missing_ok=True)


def _run_smiles_search_job(job_id: str, smiles: str, k: int, patent_codes: list[str], search_service: SearchService) -> None:
    with Session(engine) as session:
        job = job_repository.get_job(session, job_id)
        if job is None:
            return

        job_repository.start_job(session, job)

        def log_progress(level: str, message: str) -> None:
            job_repository.add_log(session, job_id=job_id, level=level, message=message)

        try:
            result = search_service.search_by_smiles(
                session,
                smiles=smiles,
                k=k,
                patent_codes=patent_codes,
                progress_callback=log_progress,
            )
            job_repository.complete_job(session, job, summary=result.model_dump())
        except Exception as exc:
            job_repository.add_log(session, job_id=job_id, level="error", message=f"SMILES search failed: {exc}")
            job_repository.fail_job(session, job, error=str(exc))


def _run_structure_search_job(
    job_id: str,
    core_smiles: Optional[str],
    r_groups: dict[str, str],
    k: int,
    search_service: SearchService,
) -> None:
    with Session(engine) as session:
        job = job_repository.get_job(session, job_id)
        if job is None:
            return

        job_repository.start_job(session, job)

        def log_progress(level: str, message: str) -> None:
            job_repository.add_log(session, job_id=job_id, level=level, message=message)

        try:
            result = search_service.search_by_structure(
                session,
                core_smiles=core_smiles,
                r_groups=r_groups,
                k=k,
                progress_callback=log_progress,
            )
            job_repository.complete_job(session, job, summary=result.model_dump())
        except Exception as exc:
            job_repository.add_log(session, job_id=job_id, level="error", message=f"Structure search failed: {exc}")
            job_repository.fail_job(session, job, error=str(exc))


@router.post("/image", response_model=SearchResponse)
async def search_image(
    file: UploadFile = File(...),
    k: int = Form(default=5),
    patent_codes: list[str] = Form(default=[]),
    session: Session = Depends(get_session),
    search_service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    return await search_service.search_by_image(session, upload=file, k=k, patent_codes=patent_codes)


@router.post("/image-job", response_model=JobAcceptedResponse)
async def search_image_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    k: int = Form(default=5),
    patent_codes: list[str] = Form(default=[]),
    session: Session = Depends(get_session),
    search_service: SearchService = Depends(get_search_service),
) -> JobAcceptedResponse:
    settings = get_settings()
    suffix = Path(file.filename or "query.png").suffix or ".png"
    with tempfile.NamedTemporaryFile(
        suffix=suffix,
        dir=settings.search_tmp_dir,
        delete=False,
    ) as temp_file:
        temp_file.write(await file.read())
        temp_path = Path(temp_file.name)

    job = job_repository.create_job(session, job_type="image_search")
    job_repository.add_log(session, job_id=job.id, message=f"Saved query image as {temp_path.name}.")
    background_tasks.add_task(_run_search_job, job.id, str(temp_path), k, patent_codes, search_service)
    return JobAcceptedResponse(job_id=job.id, status=job.status)


@router.post("/smiles", response_model=SearchResponse)
def search_smiles(
    smiles: str = Form(...),
    k: int = Form(default=5),
    patent_codes: list[str] = Form(default=[]),
    session: Session = Depends(get_session),
    search_service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    return search_service.search_by_smiles(session, smiles=smiles, k=k, patent_codes=patent_codes)


@router.post("/smiles-job", response_model=JobAcceptedResponse)
def search_smiles_job(
    background_tasks: BackgroundTasks,
    smiles: str = Form(...),
    k: int = Form(default=5),
    patent_codes: list[str] = Form(default=[]),
    session: Session = Depends(get_session),
    search_service: SearchService = Depends(get_search_service),
) -> JobAcceptedResponse:
    job = job_repository.create_job(session, job_type="smiles_search")
    job_repository.add_log(session, job_id=job.id, message="Received SMILES query.")
    background_tasks.add_task(_run_smiles_search_job, job.id, smiles, k, patent_codes, search_service)
    return JobAcceptedResponse(job_id=job.id, status=job.status)


@router.post("/structure-job", response_model=JobAcceptedResponse)
def search_structure_job(
    background_tasks: BackgroundTasks,
    payload: StructureSearchRequest,
    session: Session = Depends(get_session),
    search_service: SearchService = Depends(get_search_service),
) -> JobAcceptedResponse:
    job = job_repository.create_job(session, job_type="structure_search")
    job_repository.add_log(session, job_id=job.id, message="Received structure search query.")
    background_tasks.add_task(
        _run_structure_search_job,
        job.id,
        payload.core_smiles,
        payload.r_groups,
        payload.k,
        search_service,
    )
    return JobAcceptedResponse(job_id=job.id, status=job.status)
