from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlmodel import Session

from app.db.session import engine, get_session
from app.core.dependencies import get_extraction_service, get_patent_fetch_service
from app.models.enums import ExtractionStatus
from app.repositories.compound_image_repository import CompoundImageRepository
from app.repositories.job_repository import JobRepository
from app.repositories.patent_repository import PatentRepository
from app.schemas.job import JobAcceptedResponse
from app.schemas.patent_metadata import PatentMetadataItem, PatentMetadataResponse, PatentMetadataSummary
from app.schemas.patent import PatentBatchItemResult, PatentBatchRequest
from app.services.extraction_service import ExtractionService
from app.services.patent_fetch_service import PatentFetchService


router = APIRouter(prefix="/api/patents", tags=["patents"])

patent_repository = PatentRepository()
compound_repository = CompoundImageRepository()
job_repository = JobRepository()


@router.get("/metadata", response_model=PatentMetadataResponse)
def list_patent_metadata(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=200),
    patent_code: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
) -> PatentMetadataResponse:
    rows, summary, total = patent_repository.list_metadata(
        session,
        offset=offset,
        limit=limit,
        patent_code=patent_code.strip() if patent_code else None,
    )
    items = [
        PatentMetadataItem(
            patent_id=row["patent"].id or 0,
            patent_code=row["patent"].patent_slug,
            source_url=row["patent"].source_url,
            extraction_status=row["patent"].extraction_status.value,
            total_compounds=int(row["total_compounds"]),
            processed_compounds=int(row["processed_compounds"]),
            unprocessed_compounds=int(row["unprocessed_compounds"]),
            failed_compounds=int(row["failed_compounds"]),
            created_at=row["patent"].created_at.isoformat(),
            last_error=row["patent"].last_error,
        )
        for row in rows
    ]
    return PatentMetadataResponse(
        items=items,
        summary=PatentMetadataSummary(**summary),
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/codes", response_model=list[str])
def list_patent_codes(session: Session = Depends(get_session)) -> list[str]:
    return patent_repository.list_slugs(session)

def _run_batch_ingest_job(
    job_id: str,
    urls: list[str],
    fetch_service: PatentFetchService,
    extraction_service: ExtractionService,
) -> None:
    with Session(engine) as session:
        job = job_repository.get_job(session, job_id)
        if job is None:
            return

        job_repository.start_job(session, job)
        job_repository.add_log(session, job_id=job_id, message=f"Starting patent ingest for {len(urls)} URL(s).")

        results: list[PatentBatchItemResult] = []

        for patent_index, raw_url in enumerate(urls, start=1):
            url = raw_url.strip()
            if not url:
                continue
            job_repository.add_log(
                session,
                job_id=job_id,
                message=f"Patent {patent_index}/{len(urls)}: fetching {url}",
            )

            try:
                existing = patent_repository.get_by_source_url(session, url)
                if existing is not None:
                    image_count = compound_repository.count_by_patent(session, existing.id)
                    if existing.extraction_status == ExtractionStatus.COMPLETED and image_count > 0:
                        message = f"Patent {patent_index}/{len(urls)} already ingested with {image_count} image(s)."
                        job_repository.add_log(session, job_id=job_id, message=message)
                        results.append(
                            PatentBatchItemResult(
                                url=url,
                                patent_id=existing.id,
                                patent_code=existing.patent_slug,
                                extracted_images=image_count,
                                extraction_status=existing.extraction_status.value,
                                error=existing.last_error,
                                duplicate=True,
                            )
                        )
                        continue

                    fetch_result = fetch_service.fetch(url)
                    job_repository.add_log(
                        session,
                        job_id=job_id,
                        message=f"Retrying failed patent {fetch_result.patent_slug}.",
                    )
                    image_records = extraction_service.extract_from_patent(
                        url=fetch_result.source_url,
                        patent_slug=fetch_result.patent_slug,
                        pdf_bytes=fetch_result.pdf_bytes,
                    )
                    compound_repository.create_many(session, patent_id=existing.id, image_records=image_records)
                    patent_repository.update_status(
                        session,
                        existing,
                        extraction_status=ExtractionStatus.COMPLETED,
                        last_error=None,
                    )
                    job_repository.add_log(
                        session,
                        job_id=job_id,
                        message=f"Collected {len(image_records)} images for patent {fetch_result.patent_slug}.",
                    )
                    job_repository.add_log(
                        session,
                        job_id=job_id,
                        message=f"Finished ingesting patent {fetch_result.patent_slug}.",
                    )
                    results.append(
                        PatentBatchItemResult(
                            url=url,
                            patent_id=existing.id,
                            patent_code=existing.patent_slug,
                            extracted_images=len(image_records),
                            extraction_status=ExtractionStatus.COMPLETED.value,
                            duplicate=False,
                        )
                    )
                    continue

                fetch_result = fetch_service.fetch(url)
                patent = patent_repository.create(
                    session,
                    source_url=fetch_result.source_url,
                    patent_slug=fetch_result.patent_slug,
                )
                job_repository.add_log(
                    session,
                    job_id=job_id,
                    message=f"Fetched patent {fetch_result.patent_slug}. Extracting compound images.",
                )

                image_records = extraction_service.extract_from_patent(
                    url=fetch_result.source_url,
                    patent_slug=fetch_result.patent_slug,
                    pdf_bytes=fetch_result.pdf_bytes,
                )
                compound_repository.create_many(session, patent_id=patent.id, image_records=image_records)
                patent_repository.update_status(
                    session,
                    patent,
                    extraction_status=ExtractionStatus.COMPLETED,
                )
                job_repository.add_log(
                    session,
                    job_id=job_id,
                    message=f"Collected {len(image_records)} images for patent {fetch_result.patent_slug}.",
                )
                job_repository.add_log(
                    session,
                    job_id=job_id,
                    message=f"Finished ingesting patent {fetch_result.patent_slug}.",
                )
                results.append(
                    PatentBatchItemResult(
                        url=url,
                        patent_id=patent.id,
                        patent_code=patent.patent_slug,
                        extracted_images=len(image_records),
                        extraction_status=ExtractionStatus.COMPLETED.value,
                    )
                )
            except Exception as exc:
                existing = patent_repository.get_by_source_url(session, url)
                if existing is None:
                    slug = "unknown"
                    try:
                        slug = fetch_service.validate_google_patents_url(url)
                    except Exception:
                        pass
                    patent = patent_repository.create(
                        session,
                        source_url=url,
                        patent_slug=slug,
                        extraction_status=ExtractionStatus.FAILED,
                        last_error=str(exc),
                    )
                    patent_id = patent.id
                else:
                    patent_repository.update_status(
                        session,
                        existing,
                        extraction_status=ExtractionStatus.FAILED,
                        last_error=str(exc),
                    )
                    patent_id = existing.id

                job_repository.add_log(
                    session,
                    job_id=job_id,
                    level="error",
                    message=f"Patent ingest failed for {url}: {exc}",
                )
                results.append(
                    PatentBatchItemResult(
                        url=url,
                        patent_id=patent_id,
                        patent_code=existing.patent_slug if existing is not None else slug,
                        extracted_images=0,
                        extraction_status=ExtractionStatus.FAILED.value,
                        error=str(exc),
                    )
                )

        job_repository.add_log(session, job_id=job_id, message="Finished patent ingest job.")
        job_repository.complete_job(
            session,
            job,
            summary={"results": [result.model_dump() for result in results]},
        )


@router.post("/batch", response_model=JobAcceptedResponse)
def batch_ingest_patents(
    payload: PatentBatchRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    fetch_service: PatentFetchService = Depends(get_patent_fetch_service),
    extraction_service: ExtractionService = Depends(get_extraction_service),
) -> JobAcceptedResponse:
    job = job_repository.create_job(session, job_type="patent_ingest")
    background_tasks.add_task(_run_batch_ingest_job, job.id, payload.urls, fetch_service, extraction_service)
    return JobAcceptedResponse(job_id=job.id, status=job.status)
