from __future__ import annotations

from types import SimpleNamespace

from app.services.core_recommendation_service import CoreRecommendationService


class _FakeChemBertaService:
    def smiles_to_embedding(self, smiles: str) -> list[float]:
        return [0.1, 0.2, 0.3]


class _FakeVectorIndexService:
    def __init__(self, results: list[dict[str, float | int]]) -> None:
        self._results = results

    def search(self, embedding: list[float], k: int) -> list[dict[str, float | int]]:
        return self._results


def test_get_similar_cores_uses_stable_representative_labeled_core_per_series():
    service = CoreRecommendationService(
        chemberta_service=_FakeChemBertaService(),
        vector_index_service=_FakeVectorIndexService(
            [
                {"image_id": 1, "distance": 0.1},
                {"image_id": 2, "distance": 0.2},
                {"image_id": 3, "distance": 0.3},
            ]
        ),
    )
    service.core_candidate_repository = SimpleNamespace(
        get_preferred_by_compound_ids=lambda session, ids: {
            1: SimpleNamespace(compound_id=1, reduced_core="c1ccccc1", core_smiles="c1ccc([*:2])cc1"),
            2: SimpleNamespace(compound_id=2, reduced_core="c1ccccc1", core_smiles="c1ccc([*:1])cc1"),
            3: SimpleNamespace(compound_id=3, reduced_core="c1ccccc1", core_smiles="c1ccc([*:1])cc1"),
        }
    )

    results = service.get_similar_cores(session=None, core_smiles="CCO", k=5)

    assert len(results) == 1
    assert results[0].core_smiles == "c1ccccc1"
    assert results[0].apply_core_smiles == "c1ccc([*:1])cc1"
    assert results[0].support_count == 3
