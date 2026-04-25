from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session

from app.core.logging import get_logger
from app.repositories.compound_r_group_repository import CompoundRGroupRepository
from app.services.core_recommendation_service import CoreRecommendationService


@dataclass(frozen=True)
class RGroupSuggestionResult:
    rgroup_smiles: str
    count: int
    reason: str


@dataclass
class _RGroupAggregate:
    rgroup_smiles: str
    total_count: int = 0
    exact_count: int = 0


class RGroupRecommendationService:
    def __init__(
        self,
        *,
        core_recommendation_service: CoreRecommendationService,
    ) -> None:
        self.core_recommendation_service = core_recommendation_service
        self.r_group_repository = CompoundRGroupRepository()
        self.logger = get_logger(__name__)

    def _accumulate_rows(
        self,
        aggregates: dict[str, _RGroupAggregate],
        *,
        rows,
        exact_match: bool,
    ) -> None:
        for row in rows:
            rgroup_smiles = row.r_group.strip()
            if not rgroup_smiles:
                continue
            aggregate = aggregates.setdefault(rgroup_smiles, _RGroupAggregate(rgroup_smiles=rgroup_smiles))
            aggregate.total_count += 1
            if exact_match:
                aggregate.exact_count += 1

    def get_rgroup_suggestions(
        self,
        session: Session,
        *,
        core_smiles: str,
        attachment_point: str,
        k: int,
    ) -> list[RGroupSuggestionResult]:
        query_core_smiles = core_smiles.strip()
        query_attachment_point = attachment_point.strip()
        if not query_core_smiles:
            raise ValueError("core_smiles must not be empty")
        if not query_attachment_point:
            raise ValueError("attachment_point must not be empty")

        direct_rows = self.r_group_repository.list_by_core_smiles_and_label(
            session,
            core_smiles=query_core_smiles,
            r_label=query_attachment_point,
        )
        if not direct_rows:
            direct_rows = self.r_group_repository.list_by_reduced_core_and_label(
                session,
                reduced_core=query_core_smiles,
                r_label=query_attachment_point,
            )
        matched_molecule_count = len({row.compound_id for row in direct_rows})
        self.logger.info(
            "Matched %s molecules for core %s at attachment point %s.",
            matched_molecule_count,
            query_core_smiles,
            query_attachment_point,
        )

        aggregates: dict[str, _RGroupAggregate] = {}
        self._accumulate_rows(aggregates, rows=direct_rows, exact_match=True)

        fallback_triggered = len(aggregates) < k
        self.logger.info(
            "R-group fallback triggered for core %s at %s: %s",
            query_core_smiles,
            query_attachment_point,
            fallback_triggered,
        )

        if fallback_triggered:
            similar_cores = self.core_recommendation_service.get_similar_cores(
                session,
                core_smiles=query_core_smiles,
                k=max(k * 3, k),
            )
            for similar_core in similar_cores:
                candidate_core_smiles = similar_core.core_smiles.strip()
                if not candidate_core_smiles or candidate_core_smiles == query_core_smiles:
                    continue

                similar_rows = self.r_group_repository.list_by_core_smiles_and_label(
                    session,
                    core_smiles=candidate_core_smiles,
                    r_label=query_attachment_point,
                )
                if not similar_rows:
                    similar_rows = self.r_group_repository.list_by_reduced_core_and_label(
                        session,
                        reduced_core=candidate_core_smiles,
                        r_label=query_attachment_point,
                    )
                self._accumulate_rows(aggregates, rows=similar_rows, exact_match=False)

        ranked = sorted(
            aggregates.values(),
            key=lambda item: (
                -int(item.exact_count > 0),
                -item.total_count,
                -item.exact_count,
                item.rgroup_smiles,
            ),
        )

        return [
            RGroupSuggestionResult(
                rgroup_smiles=item.rgroup_smiles,
                count=item.total_count,
                reason=(
                    f"frequent at {query_attachment_point}"
                    if item.exact_count > 0
                    else f"frequent at {query_attachment_point} on similar core"
                ),
            )
            for item in ranked[:k]
        ]
