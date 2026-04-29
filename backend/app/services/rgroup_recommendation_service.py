from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session

from app.core.logging import get_logger
from app.repositories.compound_core_candidate_repository import CompoundCoreCandidateRepository
from app.repositories.compound_core_candidate_r_group_repository import CompoundCoreCandidateRGroupRepository
from app.services.core_recommendation_service import CoreRecommendationService
from app.services.scaffold_analysis import ScaffoldInput, analyze_scaffolds
from app.services.smiles_validation import validate_and_standardize_smiles


@dataclass(frozen=True)
class RGroupSuggestionResult:
    rgroup_smiles: str
    count: int
    reason: str
    compound_ids: list[int]
    exact_match: bool


@dataclass
class _RGroupAggregate:
    rgroup_smiles: str
    total_count: int = 0
    exact_count: int = 0
    compound_ids: set[int] | None = None

    def __post_init__(self) -> None:
        if self.compound_ids is None:
            self.compound_ids = set()


@dataclass(frozen=True)
class ExactCoreRGroupColumnResult:
    attachment_point: str
    items: list[RGroupSuggestionResult]


@dataclass(frozen=True)
class ExactCoreRGroupRecommendationsResult:
    query_core_smiles: str
    attachment_points: list[str]
    exact_core_found: bool
    columns: list[ExactCoreRGroupColumnResult]


class RGroupRecommendationService:
    def __init__(
        self,
        *,
        core_recommendation_service: CoreRecommendationService,
    ) -> None:
        self.core_recommendation_service = core_recommendation_service
        self.core_candidate_repository = CompoundCoreCandidateRepository()
        self.r_group_repository = CompoundCoreCandidateRGroupRepository()
        self.logger = get_logger(__name__)

    @staticmethod
    def _resolve_attachment_points(query_smiles: str) -> list[str]:
        validation = validate_and_standardize_smiles(query_smiles)
        if validation.mol is None:
            return []
        assignments = analyze_scaffolds([ScaffoldInput(compound_id=1, mol=validation.mol)])
        return [item.strip() for item in assignments[1].attachment_points if item.strip()]

    def _accumulate_rows(
        self,
        aggregates: dict[str, _RGroupAggregate],
        *,
        rows,
        exact_match: bool,
    ) -> None:
        for row in rows:
            rgroup_smiles = row.r_group_smiles.strip()
            if not rgroup_smiles:
                continue
            aggregate = aggregates.setdefault(rgroup_smiles, _RGroupAggregate(rgroup_smiles=rgroup_smiles))
            aggregate.total_count += 1
            aggregate.compound_ids.add(int(row.compound_id))
            if exact_match:
                aggregate.exact_count += 1

    @staticmethod
    def _rank_aggregates(aggregates: dict[str, _RGroupAggregate]) -> list[_RGroupAggregate]:
        return sorted(
            aggregates.values(),
            key=lambda item: (
                -int(item.exact_count > 0),
                -item.total_count,
                -item.exact_count,
                item.rgroup_smiles,
            ),
        )

    def _build_suggestion_results(
        self,
        ranked: list[_RGroupAggregate],
        *,
        query_attachment_point: str,
        k: int,
    ) -> list[RGroupSuggestionResult]:
        return [
            RGroupSuggestionResult(
                rgroup_smiles=item.rgroup_smiles,
                count=item.total_count,
                # reason=(
                #     f"frequent at {query_attachment_point}"
                #     if item.exact_count > 0
                #     else f"frequent at {query_attachment_point} on similar core"
                # ),
                reason='',
                compound_ids=sorted(item.compound_ids),
                exact_match=item.exact_count > 0,
            )
            for item in ranked[:k]
        ]

    def get_exact_core_rgroup_recommendations(
        self,
        session: Session,
        *,
        query_smiles: str,
        attachment_points: list[str] | None,
        k: int,
    ) -> ExactCoreRGroupRecommendationsResult:
        normalized_query = query_smiles.strip()
        if not normalized_query:
            raise ValueError("query_smiles must not be empty")

        query_core_smiles = self.core_recommendation_service._resolve_query_core_smiles(normalized_query)
        resolved_attachment_points = [item.strip() for item in (attachment_points or []) if item.strip()]

        if not resolved_attachment_points:
            resolved_attachment_points = self._resolve_attachment_points(normalized_query)

        exact_core_found = self.core_candidate_repository.exists_by_core_smiles_or_reduced_core(
            session,
            query_core=query_core_smiles,
        )

        columns: list[ExactCoreRGroupColumnResult] = []
        for attachment_point in resolved_attachment_points:
            aggregates: dict[str, _RGroupAggregate] = {}
            direct_rows = self.r_group_repository.list_by_core_smiles_and_label(
                session,
                core_smiles=query_core_smiles,
                r_label=attachment_point,
            )
            if not direct_rows:
                direct_rows = self.r_group_repository.list_by_reduced_core_and_label(
                    session,
                    reduced_core=query_core_smiles,
                    r_label=attachment_point,
                )
            self._accumulate_rows(aggregates, rows=direct_rows, exact_match=True)
            columns.append(
                ExactCoreRGroupColumnResult(
                    attachment_point=attachment_point,
                    items=self._build_suggestion_results(
                        self._rank_aggregates(aggregates),
                        query_attachment_point=attachment_point,
                        k=k,
                    ),
                )
            )

        return ExactCoreRGroupRecommendationsResult(
            query_core_smiles=query_core_smiles,
            attachment_points=resolved_attachment_points,
            exact_core_found=exact_core_found,
            columns=columns,
        )

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

        ranked = self._rank_aggregates(aggregates)
        return self._build_suggestion_results(
            ranked,
            query_attachment_point=query_attachment_point,
            k=k,
        )
