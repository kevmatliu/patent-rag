from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Iterable, Sequence

from sqlalchemy import func
from sqlmodel import Session, asc, desc, select

from app.models.compound_image import CompoundImage
from app.models.enums import ProcessingStatus, ValidationStatus
from app.models.patent import Patent
from app.repositories.compound_core_candidate_repository import CompoundCoreCandidateRepository
from app.repositories.compound_core_candidate_r_group_repository import CompoundCoreCandidateRGroupRepository


class CompoundImageRepository:
    def __init__(self) -> None:
        self.core_candidate_repository = CompoundCoreCandidateRepository()
        self.r_group_repository = CompoundCoreCandidateRGroupRepository()

    def create_many(
        self,
        session: Session,
        *,
        patent_id: int,
        image_records: Sequence[dict[str, object]],
    ) -> list[CompoundImage]:
        items: list[CompoundImage] = []
        for record in image_records:
            item = CompoundImage(
                patent_id=patent_id,
                image_path=str(record["image_path"]),
                page_number=record.get("page_number"),
            )
            session.add(item)
            items.append(item)
        session.commit()
        for item in items:
            session.refresh(item)
        return items

    def count_unprocessed(self, session: Session) -> int:
        statement = (
            select(func.count())
            .select_from(CompoundImage)
            .where(CompoundImage.processing_status == ProcessingStatus.PENDING)
        )
        return session.exec(statement).one()

    def count_by_patent(self, session: Session, patent_id: int) -> int:
        statement = (
            select(func.count())
            .select_from(CompoundImage)
            .where(CompoundImage.patent_id == patent_id)
        )
        return session.exec(statement).one()

    def list_unprocessed(
        self,
        session: Session,
        *,
        limit: int,
        order: str,
        patent_codes: Sequence[str] | None = None,
        compound_ids: Sequence[int] | None = None,
    ) -> list[CompoundImage]:
        ordering = asc(CompoundImage.created_at) if order == "oldest" else desc(CompoundImage.created_at)
        statement = select(CompoundImage).where(CompoundImage.processing_status == ProcessingStatus.PENDING)
        if patent_codes:
            statement = (
                statement.join(Patent, Patent.id == CompoundImage.patent_id)
                .where(Patent.patent_slug.in_(list(patent_codes)))
            )
        if compound_ids:
            statement = statement.where(CompoundImage.id.in_(list(compound_ids)))
        statement = statement.order_by(ordering).limit(limit)
        return list(session.exec(statement).all())

    def list_by_patent(self, session: Session, patent_id: int) -> list[CompoundImage]:
        statement = (
            select(CompoundImage)
            .where(CompoundImage.patent_id == patent_id)
            .order_by(asc(CompoundImage.created_at), asc(CompoundImage.id))
        )
        return list(session.exec(statement).all())

    def mark_processing(self, session: Session, image: CompoundImage) -> CompoundImage:
        image.processing_status = ProcessingStatus.PROCESSING
        image.updated_at = datetime.now(timezone.utc)
        image.last_error = None
        session.add(image)
        session.commit()
        session.refresh(image)
        return image

    def mark_processed(
        self,
        session: Session,
        image: CompoundImage,
        *,
        smiles: str,
        embedding: list[float],
    ) -> CompoundImage:
        image.processing_status = ProcessingStatus.PROCESSED
        image.smiles = smiles
        image.embedding = json.dumps(embedding)
        image.last_error = None
        image.updated_at = datetime.now(timezone.utc)
        session.add(image)
        session.commit()
        session.refresh(image)
        return image

    def mark_failed(self, session: Session, image: CompoundImage, *, error: str) -> CompoundImage:
        image.processing_status = ProcessingStatus.FAILED
        image.last_error = error
        image.updated_at = datetime.now(timezone.utc)
        session.add(image)
        session.commit()
        session.refresh(image)
        return image

    def get_by_ids(self, session: Session, image_ids: Iterable[int]) -> list[CompoundImage]:
        ids = list(image_ids)
        if not ids:
            return []
        statement = select(CompoundImage).where(CompoundImage.id.in_(ids))
        return list(session.exec(statement).all())

    def get_search_rows(self, session: Session, image_ids: Iterable[int]) -> list[tuple[CompoundImage, Patent]]:
        ids = list(image_ids)
        if not ids:
            return []
        statement = (
            select(CompoundImage, Patent)
            .join(Patent, Patent.id == CompoundImage.patent_id)
            .where(CompoundImage.id.in_(ids))
        )
        return list(session.exec(statement).all())

    def list_indexable(self, session: Session) -> list[CompoundImage]:
        statement = select(CompoundImage).where(CompoundImage.embedding.is_not(None))
        return list(session.exec(statement).all())

    def reset_for_reprocess(self, session: Session, *, compound_ids: Sequence[int]) -> int:
        ids = list(compound_ids)
        if not ids:
            return 0
        items = self.get_by_ids(session, ids)
        self.core_candidate_repository.delete_by_compound_ids(session, ids)
        self.r_group_repository.delete_by_compound_ids(session, ids)
        now = datetime.now(timezone.utc)
        for item in items:
            item.processing_status = ProcessingStatus.PENDING
            item.smiles = None
            item.canonical_smiles = None
            item.embedding = None
            item.last_error = None
            item.is_compound = None
            item.validation_status = ValidationStatus.UNPROCESSED
            item.validation_error = None
            item.is_duplicate_within_patent = False
            item.duplicate_of_compound_id = None
            item.kept_for_series_analysis = False
            item.pipeline_version = None
            item.updated_at = now
            session.add(item)
        session.commit()
        return len(items)

    def delete_by_ids(self, session: Session, *, compound_ids: Sequence[int]) -> int:
        ids = list(compound_ids)
        items = self.get_by_ids(session, ids)
        count = len(items)
        self.core_candidate_repository.delete_by_compound_ids(session, ids)
        self.r_group_repository.delete_by_compound_ids(session, ids)
        for item in items:
            session.delete(item)
        session.commit()
        return count

    def list_browser_rows(
        self,
        session: Session,
        *,
        offset: int,
        limit: int,
        patent_code: str | None = None,
    ) -> tuple[list[tuple[CompoundImage, Patent]], int]:
        total_statement = select(func.count()).select_from(CompoundImage).join(Patent, Patent.id == CompoundImage.patent_id)
        statement = select(CompoundImage, Patent).join(Patent, Patent.id == CompoundImage.patent_id)
        if patent_code:
            total_statement = total_statement.where(Patent.patent_slug == patent_code)
            statement = statement.where(Patent.patent_slug == patent_code)
        total = session.exec(total_statement).one()
        statement = statement.order_by(desc(CompoundImage.created_at)).offset(offset).limit(limit)
        rows = list(session.exec(statement).all())
        return rows, total
