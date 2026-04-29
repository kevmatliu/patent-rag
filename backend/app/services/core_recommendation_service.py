from __future__ import annotations

from dataclasses import dataclass
from collections import Counter

from sqlmodel import Session

from app.core.logging import get_logger
from app.repositories.compound_core_candidate_repository import CompoundCoreCandidateRepository
from app.services.scaffold_analysis import ScaffoldInput, analyze_scaffolds
from app.services.smiles_validation import validate_and_standardize_smiles
from app.services.chemberta_service import ChemBertaService
from app.services.vector_index_service import VectorIndexService


@dataclass(frozen=True)
class SimilarCoreResult:
    core_smiles: str
    score: float
    support_count: int
    apply_core_smiles: str = ""
    reason: str = ""
    # reason: str = "embedding similarity"
    compound_ids: list[int] | None = None
    exact_match: bool = False


class CoreRecommendationService:
    def __init__(
        self,
        *,
        chemberta_service: ChemBertaService,
        vector_index_service: VectorIndexService,
    ) -> None:
        self.chemberta_service = chemberta_service
        self.vector_index_service = vector_index_service
        self.core_candidate_repository = CompoundCoreCandidateRepository()
        self.logger = get_logger(__name__)

    @staticmethod
    def _distance_to_score(distance: float) -> float:
        return round(1.0 / (1.0 + max(distance, 0.0)), 6)

    @staticmethod
    def _resolve_query_core_smiles(smiles_or_core: str) -> str:
        validation = validate_and_standardize_smiles(smiles_or_core)
        if validation.mol is None:
            return smiles_or_core.strip()

        assignments = analyze_scaffolds([ScaffoldInput(compound_id=1, mol=validation.mol)])
        reduced_core = assignments[1].reduced_core
        if reduced_core:
            return reduced_core.strip()
        return validation.canonical_smiles or smiles_or_core.strip()

    @staticmethod
    def _resolve_display_core(item) -> str:
        return (item.reduced_core or item.core_smiles or "").strip()

    @staticmethod
    def _resolve_apply_core(item) -> str:
        return (item.core_smiles or item.reduced_core or "").strip()

    def get_similar_cores(
        self,
        session: Session,
        *,
        core_smiles: str,
        k: int,
    ) -> list[SimilarCoreResult]:
        query_core_smiles = core_smiles.strip()
        if not query_core_smiles:
            raise ValueError("core_smiles must not be empty")

        query_core_smiles = self._resolve_query_core_smiles(query_core_smiles)

        query_embedding = self.chemberta_service.smiles_to_embedding(query_core_smiles)

        search_limit = max(k * 5, k)
        raw_results = self.vector_index_service.search(query_embedding, search_limit)
        self.logger.info(
            "FAISS query results for core %s: %s",
            query_core_smiles,
            raw_results,
        )
        self.logger.info(
            "FAISS returned %s compound candidates for core %s.",
            len(raw_results),
            query_core_smiles,
        )

        result_ids = [int(item["image_id"]) for item in raw_results]
        candidate_by_compound_id = self.core_candidate_repository.get_preferred_by_compound_ids(session, result_ids)

        candidates = list(candidate_by_compound_id.values())
        reduced_core_values = sorted({self._resolve_display_core(item) for item in candidates if self._resolve_display_core(item)})
        support_counts = {value: 0 for value in reduced_core_values}
        representative_apply_cores: dict[str, str] = {}
        apply_core_variants: dict[str, Counter[str]] = {}
        compound_ids_by_core: dict[str, set[int]] = {}
        for item in candidates:
            resolved_display_core = self._resolve_display_core(item)
            if resolved_display_core in support_counts:
                support_counts[resolved_display_core] += 1
                compound_ids_by_core.setdefault(resolved_display_core, set()).add(int(item.compound_id))
                apply_core = self._resolve_apply_core(item)
                if apply_core:
                    apply_core_variants.setdefault(resolved_display_core, Counter())[apply_core] += 1

        for resolved_display_core, counts in apply_core_variants.items():
            representative_apply_cores[resolved_display_core] = sorted(
                counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[0][0]

        unique_results: list[SimilarCoreResult] = []
        seen_core_smiles: set[str] = set()
        for item in raw_results:
            image_id = int(item["image_id"])
            candidate = candidate_by_compound_id.get(image_id)
            if candidate is None:
                continue

            resolved_display_core = self._resolve_display_core(candidate)
            resolved_apply_core = representative_apply_cores.get(
                resolved_display_core,
                self._resolve_apply_core(candidate),
            )
            if not resolved_display_core or resolved_display_core in seen_core_smiles:
                continue

            seen_core_smiles.add(resolved_display_core)
            unique_results.append(
                SimilarCoreResult(
                    core_smiles=resolved_display_core,
                    apply_core_smiles=resolved_apply_core,
                    score=self._distance_to_score(float(item["distance"])),
                    support_count=support_counts.get(resolved_display_core, 1),
                    compound_ids=sorted(compound_ids_by_core.get(resolved_display_core, set())),
                    exact_match=resolved_display_core == query_core_smiles,
                )
            )
            if len(unique_results) >= k:
                break

        self.logger.info(
            "Resolved %s unique similar core candidates for query %s.",
            len(unique_results),
            query_core_smiles,
        )
        return unique_results
