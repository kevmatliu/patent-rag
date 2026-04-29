from __future__ import annotations

from collections.abc import Iterable, Sequence

from sqlalchemy import delete
from sqlmodel import Session, asc, select

from app.models.compound_core_candidate import CompoundCoreCandidate
from app.models.compound_core_candidate_r_group import CompoundCoreCandidateRGroup


class CompoundCoreCandidateRGroupRepository:
    def delete_by_patent(self, session: Session, patent_id: int) -> None:
        session.exec(delete(CompoundCoreCandidateRGroup).where(CompoundCoreCandidateRGroup.patent_id == patent_id))

    def delete_by_compound_ids(self, session: Session, compound_ids: Sequence[int]) -> None:
        ids = list(compound_ids)
        if not ids:
            return
        session.exec(delete(CompoundCoreCandidateRGroup).where(CompoundCoreCandidateRGroup.compound_id.in_(ids)))

    def create_many(self, session: Session, rows: Sequence[CompoundCoreCandidateRGroup]) -> None:
        for row in rows:
            session.add(row)

    def list_by_core_candidate_id(
        self,
        session: Session,
        core_candidate_id: int,
    ) -> list[CompoundCoreCandidateRGroup]:
        statement = (
            select(CompoundCoreCandidateRGroup)
            .where(CompoundCoreCandidateRGroup.core_candidate_id == core_candidate_id)
            .order_by(
                asc(CompoundCoreCandidateRGroup.attachment_index),
                asc(CompoundCoreCandidateRGroup.r_label),
                asc(CompoundCoreCandidateRGroup.id),
            )
        )
        return list(session.exec(statement).all())

    def list_by_core_smiles_and_label(
        self,
        session: Session,
        *,
        core_smiles: str,
        r_label: str,
    ) -> list[CompoundCoreCandidateRGroup]:
        statement = (
            select(CompoundCoreCandidateRGroup)
            .join(CompoundCoreCandidate, CompoundCoreCandidate.id == CompoundCoreCandidateRGroup.core_candidate_id)
            .where(
                CompoundCoreCandidate.core_smiles == core_smiles,
                CompoundCoreCandidateRGroup.r_label == r_label,
            )
            .order_by(
                CompoundCoreCandidateRGroup.compound_id,
                CompoundCoreCandidateRGroup.attachment_index,
                CompoundCoreCandidateRGroup.id,
            )
        )
        return list(session.exec(statement).all())

    def list_by_reduced_core_and_label(
        self,
        session: Session,
        *,
        reduced_core: str,
        r_label: str,
    ) -> list[CompoundCoreCandidateRGroup]:
        statement = (
            select(CompoundCoreCandidateRGroup)
            .join(CompoundCoreCandidate, CompoundCoreCandidate.id == CompoundCoreCandidateRGroup.core_candidate_id)
            .where(
                CompoundCoreCandidate.reduced_core == reduced_core,
                CompoundCoreCandidateRGroup.r_label == r_label,
            )
            .order_by(
                CompoundCoreCandidateRGroup.compound_id,
                CompoundCoreCandidateRGroup.attachment_index,
                CompoundCoreCandidateRGroup.id,
            )
        )
        return list(session.exec(statement).all())

    def list_by_compound_ids(self, session: Session, compound_ids: Iterable[int]) -> list[CompoundCoreCandidateRGroup]:
        ids = list(compound_ids)
        if not ids:
            return []
        statement = (
            select(CompoundCoreCandidateRGroup)
            .where(CompoundCoreCandidateRGroup.compound_id.in_(ids))
            .order_by(
                CompoundCoreCandidateRGroup.compound_id,
                CompoundCoreCandidateRGroup.attachment_index,
                CompoundCoreCandidateRGroup.r_label,
            )
        )
        return list(session.exec(statement).all())
