from __future__ import annotations

from collections.abc import Iterable, Sequence

from sqlalchemy import delete
from sqlmodel import Session, asc, desc, select

from app.models.compound_core_candidate import CompoundCoreCandidate


class CompoundCoreCandidateRepository:
    def delete_by_patent(self, session: Session, patent_id: int) -> None:
        session.exec(delete(CompoundCoreCandidate).where(CompoundCoreCandidate.patent_id == patent_id))

    def delete_by_compound_ids(self, session: Session, compound_ids: Sequence[int]) -> None:
        ids = list(compound_ids)
        if not ids:
            return
        session.exec(delete(CompoundCoreCandidate).where(CompoundCoreCandidate.compound_id.in_(ids)))

    def create_many(self, session: Session, rows: Sequence[CompoundCoreCandidate]) -> None:
        for row in rows:
            session.add(row)

    def list_by_compound_id(self, session: Session, compound_id: int) -> list[CompoundCoreCandidate]:
        statement = (
            select(CompoundCoreCandidate)
            .where(CompoundCoreCandidate.compound_id == compound_id)
            .order_by(
                desc(CompoundCoreCandidate.is_selected),
                asc(CompoundCoreCandidate.candidate_rank),
                asc(CompoundCoreCandidate.id),
            )
        )
        return list(session.exec(statement).all())

    def list_by_compound_ids(self, session: Session, compound_ids: Iterable[int]) -> list[CompoundCoreCandidate]:
        ids = list(compound_ids)
        if not ids:
            return []
        statement = (
            select(CompoundCoreCandidate)
            .where(CompoundCoreCandidate.compound_id.in_(ids))
            .order_by(
                asc(CompoundCoreCandidate.compound_id),
                desc(CompoundCoreCandidate.is_selected),
                asc(CompoundCoreCandidate.candidate_rank),
                asc(CompoundCoreCandidate.id),
            )
        )
        return list(session.exec(statement).all())

    def get_by_id(self, session: Session, core_candidate_id: int) -> CompoundCoreCandidate | None:
        return session.get(CompoundCoreCandidate, core_candidate_id)

    def exists_by_core_smiles_or_reduced_core(
        self,
        session: Session,
        *,
        query_core: str,
    ) -> bool:
        normalized_query = query_core.strip()
        if not normalized_query:
            return False
        statement = (
            select(CompoundCoreCandidate.id)
            .where(
                (CompoundCoreCandidate.core_smiles == normalized_query)
                | (CompoundCoreCandidate.reduced_core == normalized_query)
            )
            .limit(1)
        )
        return session.exec(statement).first() is not None

    def get_preferred_by_compound_ids(
        self,
        session: Session,
        compound_ids: Iterable[int],
    ) -> dict[int, CompoundCoreCandidate]:
        preferred: dict[int, CompoundCoreCandidate] = {}
        for candidate in self.list_by_compound_ids(session, compound_ids):
            if candidate.compound_id not in preferred:
                preferred[candidate.compound_id] = candidate
        return preferred

    def summarize_by_compound_ids(
        self,
        session: Session,
        compound_ids: Iterable[int],
    ) -> dict[int, dict[str, int | None]]:
        summary: dict[int, dict[str, int | None]] = {}
        for candidate in self.list_by_compound_ids(session, compound_ids):
            item = summary.setdefault(
                candidate.compound_id,
                {"core_candidate_count": 0, "selected_core_candidate_id": None},
            )
            item["core_candidate_count"] = int(item["core_candidate_count"]) + 1
            if candidate.is_selected and item["selected_core_candidate_id"] is None:
                item["selected_core_candidate_id"] = candidate.id
            if item["selected_core_candidate_id"] is None:
                item["selected_core_candidate_id"] = candidate.id
        return summary
