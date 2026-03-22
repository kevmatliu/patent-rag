from __future__ import annotations

from typing import Optional

from sqlalchemy import case, func
from sqlmodel import Session, select

from app.models.compound_image import CompoundImage
from app.models.enums import ExtractionStatus
from app.models.enums import ProcessingStatus
from app.models.patent import Patent


class PatentRepository:
    def get_by_source_url(self, session: Session, source_url: str) -> Optional[Patent]:
        statement = select(Patent).where(Patent.source_url == source_url)
        return session.exec(statement).first()

    def get_by_slug(self, session: Session, patent_slug: str) -> Optional[Patent]:
        statement = select(Patent).where(Patent.patent_slug == patent_slug)
        return session.exec(statement).first()

    def create(
        self,
        session: Session,
        *,
        source_url: str,
        patent_slug: str,
        extraction_status: ExtractionStatus = ExtractionStatus.PENDING,
        last_error: Optional[str] = None,
    ) -> Patent:
        patent = Patent(
            source_url=source_url,
            patent_slug=patent_slug,
            extraction_status=extraction_status,
            last_error=last_error,
        )
        session.add(patent)
        session.commit()
        session.refresh(patent)
        return patent

    def update_status(
        self,
        session: Session,
        patent: Patent,
        *,
        extraction_status: ExtractionStatus,
        last_error: Optional[str] = None,
    ) -> Patent:
        patent.extraction_status = extraction_status
        patent.last_error = last_error
        session.add(patent)
        session.commit()
        session.refresh(patent)
        return patent

    def delete(self, session: Session, patent: Patent) -> None:
        session.delete(patent)
        session.commit()

    def list_slugs(self, session: Session) -> list[str]:
        statement = select(Patent.patent_slug).order_by(Patent.patent_slug)
        return list(session.exec(statement).all())

    def list_metadata(
        self,
        session: Session,
        *,
        offset: int,
        limit: int,
        patent_code: str | None = None,
    ) -> tuple[list[dict[str, object]], dict[str, int], int]:
        total_statement = select(func.count()).select_from(Patent)
        if patent_code:
            total_statement = total_statement.where(Patent.patent_slug.contains(patent_code))
        total = session.exec(total_statement).one()

        processed_case = case((CompoundImage.processing_status == ProcessingStatus.PROCESSED, 1), else_=0)
        pending_case = case((CompoundImage.processing_status == ProcessingStatus.PENDING, 1), else_=0)
        failed_case = case((CompoundImage.processing_status == ProcessingStatus.FAILED, 1), else_=0)

        statement = (
            select(
                Patent,
                func.count(CompoundImage.id).label("total_compounds"),
                func.sum(processed_case).label("processed_compounds"),
                func.sum(pending_case).label("unprocessed_compounds"),
                func.sum(failed_case).label("failed_compounds"),
            )
            .outerjoin(CompoundImage, CompoundImage.patent_id == Patent.id)
        )
        if patent_code:
            statement = statement.where(Patent.patent_slug.contains(patent_code))
        statement = statement.group_by(Patent.id).order_by(Patent.created_at.desc()).offset(offset).limit(limit)

        rows = []
        for patent, total_compounds, processed_compounds, unprocessed_compounds, failed_compounds in session.exec(statement).all():
            rows.append(
                {
                    "patent": patent,
                    "total_compounds": int(total_compounds or 0),
                    "processed_compounds": int(processed_compounds or 0),
                    "unprocessed_compounds": int(unprocessed_compounds or 0),
                    "failed_compounds": int(failed_compounds or 0),
                }
            )

        summary_statement = (
            select(
                func.count(func.distinct(Patent.id)).label("total_patents"),
                func.count(func.distinct(case((CompoundImage.processing_status == ProcessingStatus.PROCESSED, Patent.id), else_=None))).label("processed_patents"),
                func.count(func.distinct(case((CompoundImage.processing_status == ProcessingStatus.PENDING, Patent.id), else_=None))).label("unprocessed_patents"),
            )
            .select_from(Patent)
            .outerjoin(CompoundImage, CompoundImage.patent_id == Patent.id)
        )
        if patent_code:
            summary_statement = summary_statement.where(Patent.patent_slug.contains(patent_code))
        total_patents, processed_patents, unprocessed_patents = session.exec(summary_statement).one()
        summary = {
            "total_patents": int(total_patents or 0),
            "processed_patents": int(processed_patents or 0),
            "unprocessed_patents": int(unprocessed_patents or 0),
        }
        return rows, summary, total
