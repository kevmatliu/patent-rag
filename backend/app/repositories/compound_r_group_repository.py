from __future__ import annotations

from collections.abc import Iterable, Sequence

from sqlalchemy import delete
from sqlmodel import Session, select

from app.models.compound_image import CompoundImage
from app.models.compound_r_group import CompoundRGroup


class CompoundRGroupRepository:
    def delete_by_patent(self, session: Session, patent_id: int) -> None:
        session.exec(delete(CompoundRGroup).where(CompoundRGroup.patent_id == patent_id))

    def delete_by_compound_ids(self, session: Session, compound_ids: Sequence[int]) -> None:
        ids = list(compound_ids)
        if not ids:
            return
        session.exec(delete(CompoundRGroup).where(CompoundRGroup.compound_id.in_(ids)))

    def create_many(self, session: Session, rows: Sequence[CompoundRGroup]) -> None:
        for row in rows:
            session.add(row)

    def list_by_compound_ids(self, session: Session, compound_ids: Iterable[int]) -> list[CompoundRGroup]:
        ids = list(compound_ids)
        if not ids:
            return []
        statement = select(CompoundRGroup).where(CompoundRGroup.compound_id.in_(ids)).order_by(CompoundRGroup.compound_id, CompoundRGroup.r_label)
        return list(session.exec(statement).all())

    def list_by_compound_id(self, session: Session, compound_id: int) -> list[CompoundRGroup]:
        statement = (
            select(CompoundRGroup)
            .where(CompoundRGroup.compound_id == compound_id)
            .order_by(CompoundRGroup.r_label, CompoundRGroup.id)
        )
        return list(session.exec(statement).all())

    def list_by_core_smiles_and_label(
        self,
        session: Session,
        *,
        core_smiles: str,
        r_label: str,
    ) -> list[CompoundRGroup]:
        statement = (
            select(CompoundRGroup)
            .where(
                CompoundRGroup.core_smiles == core_smiles,
                CompoundRGroup.r_label == r_label,
            )
            .order_by(CompoundRGroup.compound_id, CompoundRGroup.id)
        )
        return list(session.exec(statement).all())

    def list_by_reduced_core_and_label(
        self,
        session: Session,
        *,
        reduced_core: str,
        r_label: str,
    ) -> list[CompoundRGroup]:
        statement = (
            select(CompoundRGroup)
            .join(CompoundImage, CompoundImage.id == CompoundRGroup.compound_id)
            .where(
                CompoundImage.reduced_core == reduced_core,
                CompoundRGroup.r_label == r_label,
            )
            .order_by(CompoundRGroup.compound_id, CompoundRGroup.id)
        )
        return list(session.exec(statement).all())
