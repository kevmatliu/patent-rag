from __future__ import annotations

from sqlmodel import Session

from app.models.compound_core_candidate import CompoundCoreCandidate
from app.models.compound_core_candidate_r_group import CompoundCoreCandidateRGroup
from app.models.patent import Patent
from app.services.core_recommendation_service import SimilarCoreResult
from app.services.rgroup_recommendation_service import RGroupRecommendationService


class StubCoreRecommendationService:
    def __init__(self, similar_cores: list[SimilarCoreResult]) -> None:
        self.similar_cores = similar_cores

    def get_similar_cores(self, session: Session, *, core_smiles: str, k: int) -> list[SimilarCoreResult]:
        _ = (session, core_smiles, k)
        return list(self.similar_cores)


def test_rgroup_recommendation_prefers_exact_core_matches(session_factory):
    with Session(session_factory) as session:
        patent = Patent(
            source_url="https://patents.google.com/patent/US20250042916A1/en",
            patent_slug="US20250042916A1",
        )
        session.add(patent)
        session.commit()
        session.refresh(patent)

        session.add_all(
            [
                CompoundCoreCandidate(id=101, compound_id=1, patent_id=patent.id, candidate_rank=1, is_selected=True, core_smiles="core-a", core_smarts="*", reduced_core="core-a"),
                CompoundCoreCandidate(id=102, compound_id=2, patent_id=patent.id, candidate_rank=1, is_selected=True, core_smiles="core-a", core_smarts="*", reduced_core="core-a"),
                CompoundCoreCandidate(id=103, compound_id=3, patent_id=patent.id, candidate_rank=1, is_selected=True, core_smiles="core-a", core_smarts="*", reduced_core="core-a"),
                CompoundCoreCandidate(id=104, compound_id=4, patent_id=patent.id, candidate_rank=1, is_selected=True, core_smiles="core-b", core_smarts="*", reduced_core="core-b"),
                CompoundCoreCandidate(id=105, compound_id=5, patent_id=patent.id, candidate_rank=1, is_selected=True, core_smiles="core-b", core_smarts="*", reduced_core="core-b"),
            ]
        )
        session.add_all(
            [
                CompoundCoreCandidateRGroup(core_candidate_id=101, compound_id=1, patent_id=patent.id, r_label="R1", r_group_smiles="Cl[*:1]", attachment_index=1),
                CompoundCoreCandidateRGroup(core_candidate_id=102, compound_id=2, patent_id=patent.id, r_label="R1", r_group_smiles="Cl[*:1]", attachment_index=1),
                CompoundCoreCandidateRGroup(core_candidate_id=103, compound_id=3, patent_id=patent.id, r_label="R1", r_group_smiles="F[*:1]", attachment_index=1),
                CompoundCoreCandidateRGroup(core_candidate_id=104, compound_id=4, patent_id=patent.id, r_label="R1", r_group_smiles="Br[*:1]", attachment_index=1),
                CompoundCoreCandidateRGroup(core_candidate_id=105, compound_id=5, patent_id=patent.id, r_label="R1", r_group_smiles="Br[*:1]", attachment_index=1),
            ]
        )
        session.commit()

        service = RGroupRecommendationService(
            core_recommendation_service=StubCoreRecommendationService(
                [SimilarCoreResult(core_smiles="core-b", apply_core_smiles="core-b", score=0.9, support_count=2)]
            )
        )
        results = service.get_rgroup_suggestions(
            session,
            core_smiles="core-a",
            attachment_point="R1",
            k=3,
        )

    assert results[0].rgroup_smiles == "Cl[*:1]"
    assert results[0].count == 2
    assert results[0].reason == "frequent at R1"
    assert results[1].rgroup_smiles == "F[*:1]"
    assert results[1].reason == "frequent at R1"
    assert results[2].rgroup_smiles == "Br[*:1]"
    assert results[2].count == 2
    assert results[2].reason == "frequent at R1 on similar core"


def test_rgroup_recommendation_uses_fallback_when_exact_core_is_sparse(session_factory):
    with Session(session_factory) as session:
        patent = Patent(
            source_url="https://patents.google.com/patent/WO2025015269A1/en",
            patent_slug="WO2025015269A1",
        )
        session.add(patent)
        session.commit()
        session.refresh(patent)

        session.add_all(
            [
                CompoundCoreCandidate(id=201, compound_id=10, patent_id=patent.id, candidate_rank=1, is_selected=True, core_smiles="core-a", core_smarts="*", reduced_core="core-a"),
                CompoundCoreCandidate(id=202, compound_id=11, patent_id=patent.id, candidate_rank=1, is_selected=True, core_smiles="core-b", core_smarts="*", reduced_core="core-b"),
                CompoundCoreCandidate(id=203, compound_id=12, patent_id=patent.id, candidate_rank=1, is_selected=True, core_smiles="core-b", core_smarts="*", reduced_core="core-b"),
                CompoundCoreCandidate(id=204, compound_id=13, patent_id=patent.id, candidate_rank=1, is_selected=True, core_smiles="core-c", core_smarts="*", reduced_core="core-c"),
            ]
        )
        session.add_all(
            [
                CompoundCoreCandidateRGroup(core_candidate_id=201, compound_id=10, patent_id=patent.id, r_label="R1", r_group_smiles="Cl[*:1]", attachment_index=1),
                CompoundCoreCandidateRGroup(core_candidate_id=202, compound_id=11, patent_id=patent.id, r_label="R1", r_group_smiles="O[*:1]", attachment_index=1),
                CompoundCoreCandidateRGroup(core_candidate_id=203, compound_id=12, patent_id=patent.id, r_label="R1", r_group_smiles="O[*:1]", attachment_index=1),
                CompoundCoreCandidateRGroup(core_candidate_id=204, compound_id=13, patent_id=patent.id, r_label="R1", r_group_smiles="N[*:1]", attachment_index=1),
            ]
        )
        session.commit()

        service = RGroupRecommendationService(
            core_recommendation_service=StubCoreRecommendationService(
                [
                    SimilarCoreResult(core_smiles="core-b", apply_core_smiles="core-b", score=0.95, support_count=2),
                    SimilarCoreResult(core_smiles="core-c", apply_core_smiles="core-c", score=0.9, support_count=1),
                ]
            )
        )
        results = service.get_rgroup_suggestions(
            session,
            core_smiles="core-a",
            attachment_point="R1",
            k=3,
        )

    assert [item.rgroup_smiles for item in results] == ["Cl[*:1]", "O[*:1]", "N[*:1]"]
    assert results[0].reason == "frequent at R1"
    assert results[1].reason == "frequent at R1 on similar core"
    assert results[1].count == 2
