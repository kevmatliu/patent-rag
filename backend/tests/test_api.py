from __future__ import annotations

import json
from pathlib import Path
import time

from app.core.dependencies import (
    get_extraction_service,
    get_patent_fetch_service,
    get_core_recommendation_service,
    get_molecule_modification_service,
    get_processing_service,
    get_rgroup_recommendation_service,
    get_search_service,
)
from app.repositories.job_repository import JobRepository
from app.models.compound_image import CompoundImage
from app.models.compound_r_group import CompoundRGroup
from app.models.enums import ExtractionStatus, ProcessingStatus
from app.models.job_log import JobLog
from app.models.job_run import JobRun
from app.models.patent import Patent
from app.repositories.compound_image_repository import CompoundImageRepository
from app.schemas.image_processing import SearchResponse, SearchResultItem
from app.services.patent_fetch_service import PatentFetchResult
from app.services.core_recommendation_service import SimilarCoreResult
from app.services.molecule_modification_service import MoleculeModificationResult
from app.services.core_recommendation_service import CoreRecommendationService
from app.services.processing_service import ProcessingService
from app.services.rgroup_recommendation_service import RGroupRecommendationService
from app.services.rgroup_recommendation_service import RGroupSuggestionResult
from sqlmodel import Session, select


class FakePatentFetchService:
    def fetch(self, url: str) -> PatentFetchResult:
        return PatentFetchResult(source_url=url, patent_slug="US20250042916A1", pdf_bytes=b"%PDF-1.4")

    def validate_google_patents_url(self, url: str) -> str:
        return "US20250042916A1"


class FakeExtractionService:
    def __init__(self, image_path: Path) -> None:
        self.image_path = image_path

    def extract_from_patent(self, url: str, patent_slug: str, pdf_bytes: bytes) -> list[dict[str, object]]:
        _ = (url, patent_slug, pdf_bytes)
        return [{"image_path": str(self.image_path), "page_number": 7}]


class FakeMolScribeService:
    name = "molscribe"
    device = "cpu"

    def image_to_smiles(self, image_path: str) -> str:
        _ = image_path
        return "CCO"


class FakeChemBertaService:
    device = "cpu"

    def smiles_to_embedding(self, smiles: str) -> list[float]:
        _ = smiles
        return [0.1, 0.2, 0.3]


class FakeVectorIndexService:
    def __init__(self) -> None:
        self.vectors: list[tuple[int, list[float]]] = []
        self.dimension = 3

    def add_vector(self, image_id: int, vector: list[float]) -> None:
        self.vectors.append((image_id, vector))

    def rebuild(self, items: list[tuple[int, list[float]]]) -> None:
        self.vectors = list(items)


class SearchableFakeVectorIndexService(FakeVectorIndexService):
    def __init__(self, results: list[dict[str, float | int]]) -> None:
        super().__init__()
        self.results = results

    def search(self, vector: list[float], limit: int) -> list[dict[str, float | int]]:
        _ = vector
        return self.results[:limit]


class FakeSearchService:
    def search_by_image_path(self, session: Session, *, image_path: Path, k: int, progress_callback=None) -> SearchResponse:
        _ = (session, image_path, k)
        if progress_callback is not None:
            progress_callback("info", "Generated query SMILES.")
        return self.search_by_smiles(session, smiles="CCO", k=k, progress_callback=progress_callback)

    def search_by_smiles(self, session: Session, *, smiles: str, k: int, progress_callback=None) -> SearchResponse:
        _ = (session, smiles, k)
        if progress_callback is not None:
            progress_callback("info", "Generated ChemBERTa embedding for query.")
        return SearchResponse(
            query_smiles="CCO",
            results=[
                SearchResultItem(
                    image_id=1,
                    similarity=0.99,
                    smiles="CCO",
                    image_url="/static/extracted/example.png",
                    patent_code="US20250042916A1",
                    page_number=7,
                    patent_source_url="https://patents.google.com/patent/US20250042916A1/en",
                )
            ],
        )

    async def search_by_image(self, session: Session, *, upload, k: int) -> SearchResponse:
        _ = (session, upload, k)
        return self.search_by_image_path(session, image_path=Path("query.png"), k=k)


class FakeCoreRecommendationService:
    def get_similar_cores(self, session: Session, *, core_smiles: str, k: int) -> list[SimilarCoreResult]:
        _ = session
        return [
            SimilarCoreResult(
                core_smiles=f"{core_smiles}-match-{index}",
                apply_core_smiles=f"{core_smiles}-apply-{index}",
                score=round(0.95 - (index * 0.05), 6),
                support_count=index + 1,
            )
            for index in range(k)
        ]


class FakeRGroupRecommendationService:
    def get_rgroup_suggestions(
        self,
        session: Session,
        *,
        core_smiles: str,
        attachment_point: str,
        k: int,
    ) -> list[RGroupSuggestionResult]:
        _ = session
        return [
            RGroupSuggestionResult(
                rgroup_smiles=f"{core_smiles}-{attachment_point}-{index}",
                count=index + 2,
                reason=f"frequent at {attachment_point}",
            )
            for index in range(k)
        ]


class FakeMoleculeModificationService:
    def apply_modification(
        self,
        *,
        current_smiles: str,
        target_core_smiles: str | None = None,
        attachment_point: str | None = None,
        rgroup_smiles: str | None = None,
    ) -> MoleculeModificationResult:
        return MoleculeModificationResult(
            smiles="CCN",
            core_smiles=target_core_smiles or f"{current_smiles}:{attachment_point}:{rgroup_smiles}",
        )


def wait_for_job(client, job_id: str, timeout_seconds: float = 2.0):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        body = response.json()
        if body["status"] in {"completed", "failed", "cancelled"}:
            return body
        time.sleep(0.05)
    raise AssertionError(f"Job {job_id} did not complete within {timeout_seconds} seconds")


def test_batch_patent_ingest(client, session_factory, tmp_path):
    image_path = tmp_path / "compound.png"
    image_path.write_bytes(b"png-image")

    app = client.app
    app.dependency_overrides[get_patent_fetch_service] = lambda: FakePatentFetchService()
    app.dependency_overrides[get_extraction_service] = lambda: FakeExtractionService(image_path)

    response = client.post(
        "/api/patents/batch",
        json={"urls": ["https://patents.google.com/patent/US20250042916A1/en"]},
    )

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    body = wait_for_job(client, job_id)
    assert body["status"] == "completed"
    assert body["summary"]["results"][0]["extraction_status"] == ExtractionStatus.COMPLETED.value
    assert body["summary"]["results"][0]["extracted_images"] == 1
    assert any("Collected 1 images" in log["message"] for log in body["logs"])


def test_batch_patent_ingest_persists_page_number(client, session_factory, tmp_path):
    image_path = tmp_path / "compound.png"
    image_path.write_bytes(b"png-image")

    client.app.dependency_overrides[get_patent_fetch_service] = lambda: FakePatentFetchService()
    client.app.dependency_overrides[get_extraction_service] = lambda: FakeExtractionService(image_path)

    response = client.post(
        "/api/patents/batch",
        json={"urls": ["https://patents.google.com/patent/US20250042916A1/en"]},
    )
    assert response.status_code == 200

    body = wait_for_job(client, response.json()["job_id"])
    assert body["status"] == "completed"

    with Session(session_factory) as session:
        patents = session.exec(select(Patent)).all()
        images = session.exec(select(CompoundImage)).all()
        assert len(patents) == 1
        assert len(images) == 1
        assert images[0].page_number == 7


def test_pdf_patent_ingest_uses_filename_as_patent_code(client, session_factory, tmp_path):
    image_path = tmp_path / "compound.png"
    image_path.write_bytes(b"png-image")

    client.app.dependency_overrides[get_extraction_service] = lambda: FakeExtractionService(image_path)

    response = client.post(
        "/api/patents/upload-pdfs",
        files={"files": ("US20250042916A1.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )

    assert response.status_code == 200
    body = wait_for_job(client, response.json()["job_id"])
    assert body["status"] == "completed"
    assert body["summary"]["results"][0]["patent_code"] == "US20250042916A1"
    assert body["summary"]["results"][0]["extracted_images"] == 1

    with Session(session_factory) as session:
        patents = session.exec(select(Patent)).all()
        assert len(patents) == 1
        assert patents[0].patent_slug == "US20250042916A1"


def test_decompose_structure_endpoint_returns_labeled_core(client):
    response = client.post("/recommend/decompose-structure", json={"current_smiles": "Clc1ccccc1"})

    assert response.status_code == 200
    body = response.json()
    assert body["canonical_smiles"] == "Clc1ccccc1"
    assert body["reduced_core"] == "c1ccccc1"
    assert body["labeled_core_smiles"] == "c1ccc([*:1])cc1"
    assert body["attachment_points"] == ["R1"]
    assert body["r_groups"] == [{"r_label": "R1", "r_group": "Cl[*:1]"}]


def test_decompose_structure_endpoint_rejects_invalid_smiles(client):
    response = client.post("/recommend/decompose-structure", json={"current_smiles": "not-a-smiles"})

    assert response.status_code == 400
    assert "RDKit could not parse SMILES" in response.json()["detail"]


def test_process_images_updates_rows(client, session_factory, tmp_path, configured_settings):
    image_path = tmp_path / "compound.png"
    image_path.write_bytes(b"png-image")

    with Session(session_factory) as session:
        patent = Patent(
            source_url="https://patents.google.com/patent/US20250042916A1/en",
            patent_slug="US20250042916A1",
        )
        session.add(patent)
        session.commit()
        session.refresh(patent)

        image = CompoundImage(patent_id=patent.id, image_path=str(image_path))
        session.add(image)
        session.commit()

    processing_service = ProcessingService(
        settings=configured_settings,
        smiles_recognition_service=FakeMolScribeService(),
        chemberta_service=FakeChemBertaService(),
        vector_index_service=FakeVectorIndexService(),
    )
    client.app.dependency_overrides[get_processing_service] = lambda: processing_service

    response = client.post("/api/images/process", json={"limit": 5, "order": "oldest"})
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    payload = wait_for_job(client, job_id)["summary"]
    assert payload["processed_count"] == 1
    assert payload["failed_count"] == 0

    with Session(session_factory) as session:
        repo = CompoundImageRepository()
        stored = repo.list_indexable(session)
        assert len(stored) == 1
        assert stored[0].smiles == "CCO"
        assert stored[0].canonical_smiles == "CCO"
        assert json.loads(stored[0].embedding) == [0.1, 0.2, 0.3]


def test_process_images_job_contains_progress_logs(client, session_factory, tmp_path, configured_settings):
    image_path = tmp_path / "compound.png"
    image_path.write_bytes(b"png-image")

    with Session(session_factory) as session:
        patent = Patent(
            source_url="https://patents.google.com/patent/US20250042916A1/en",
            patent_slug="US20250042916A1",
        )
        session.add(patent)
        session.commit()
        session.refresh(patent)

        image = CompoundImage(patent_id=patent.id, image_path=str(image_path))
        session.add(image)
        session.commit()

    processing_service = ProcessingService(
        settings=configured_settings,
        smiles_recognition_service=FakeMolScribeService(),
        chemberta_service=FakeChemBertaService(),
        vector_index_service=FakeVectorIndexService(),
    )
    client.app.dependency_overrides[get_processing_service] = lambda: processing_service

    response = client.post("/api/images/process", json={"limit": 5, "order": "oldest"})
    assert response.status_code == 200

    body = wait_for_job(client, response.json()["job_id"])
    assert body["status"] == "completed"
    assert any("running MOLSCRIBE" in log["message"] for log in body["logs"])
    assert body["summary"]["processed_count"] == 1


def test_search_image_route(client):
    client.app.dependency_overrides[get_search_service] = lambda: FakeSearchService()
    response = client.post(
        "/api/search/image",
        files={"file": ("query.png", b"fake-image", "image/png")},
        data={"k": "3"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query_smiles"] == "CCO"
    assert body["results"][0]["similarity"] == 0.99
    assert body["results"][0]["patent_code"] == "US20250042916A1"
    assert body["results"][0]["page_number"] == 7


def test_search_image_job_returns_summary_and_logs(client):
    client.app.dependency_overrides[get_search_service] = lambda: FakeSearchService()
    response = client.post(
        "/api/search/image-job",
        files={"file": ("query.png", b"fake-image", "image/png")},
        data={"k": "3"},
    )

    assert response.status_code == 200
    body = wait_for_job(client, response.json()["job_id"])
    assert body["status"] == "completed"
    assert body["summary"]["query_smiles"] == "CCO"
    assert any("Generated query SMILES" in log["message"] for log in body["logs"])


def test_search_smiles_job_returns_summary(client):
    client.app.dependency_overrides[get_search_service] = lambda: FakeSearchService()
    response = client.post(
        "/api/search/smiles-job",
        data={"smiles": "CCO", "k": "3"},
    )

    assert response.status_code == 200
    body = wait_for_job(client, response.json()["job_id"])
    assert body["status"] == "completed"
    assert body["summary"]["query_smiles"] == "CCO"


def test_recommend_similar_cores_returns_ranked_core_rows(client):
    client.app.dependency_overrides[get_core_recommendation_service] = lambda: FakeCoreRecommendationService()
    response = client.post(
        "/recommend/similar-cores",
        json={"core_smiles": "c1ccccc1", "k": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body == [
        {
            "core_smiles": "c1ccccc1-match-0",
            "apply_core_smiles": "c1ccccc1-apply-0",
            "score": 0.95,
            "support_count": 1,
            "reason": "embedding similarity",
        },
        {
            "core_smiles": "c1ccccc1-match-1",
            "apply_core_smiles": "c1ccccc1-apply-1",
            "score": 0.9,
            "support_count": 2,
            "reason": "embedding similarity",
        },
    ]


def test_recommend_rgroups_returns_ranked_rows(client):
    client.app.dependency_overrides[get_rgroup_recommendation_service] = lambda: FakeRGroupRecommendationService()
    response = client.post(
        "/recommend/rgroups",
        json={"core_smiles": "c1ccccc1", "attachment_point": "R1", "k": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body == [
        {
            "rgroup_smiles": "c1ccccc1-R1-0",
            "count": 2,
            "reason": "frequent at R1",
        },
        {
            "rgroup_smiles": "c1ccccc1-R1-1",
            "count": 3,
            "reason": "frequent at R1",
        },
    ]


def test_apply_modification_returns_updated_smiles(client):
    client.app.dependency_overrides[get_molecule_modification_service] = lambda: FakeMoleculeModificationService()
    response = client.post(
        "/recommend/apply-modification",
        json={
            "current_smiles": "CCO",
            "target_core_smiles": "c1ccc([*:1])cc1",
            "attachment_point": "R1",
            "rgroup_smiles": "Cl[*:1]",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "smiles": "CCN",
        "core_smiles": "c1ccc([*:1])cc1",
    }


def test_recommendation_endpoints_use_real_ranking_and_fallback(client, session_factory):
    with Session(session_factory) as session:
        patent = Patent(
            source_url="https://patents.google.com/patent/US20250042916A1/en",
            patent_slug="US20250042916A1",
        )
        session.add(patent)
        session.commit()
        session.refresh(patent)

        compound_a = CompoundImage(
            patent_id=patent.id,
            image_path="compound-a.png",
            smiles="Clc1ccccc1",
            canonical_smiles="Clc1ccccc1",
            validation_status="VALID",
            is_compound=True,
            core_smiles="core-a",
            reduced_core="core-a",
        )
        compound_b1 = CompoundImage(
            patent_id=patent.id,
            image_path="compound-b1.png",
            smiles="Oc1ccccc1",
            canonical_smiles="Oc1ccccc1",
            validation_status="VALID",
            is_compound=True,
            core_smiles="core-b",
            reduced_core="core-b",
        )
        compound_b2 = CompoundImage(
            patent_id=patent.id,
            image_path="compound-b2.png",
            smiles="Nc1ccccc1",
            canonical_smiles="Nc1ccccc1",
            validation_status="VALID",
            is_compound=True,
            core_smiles="core-b",
            reduced_core="core-b",
        )
        session.add_all([compound_a, compound_b1, compound_b2])
        session.commit()
        session.refresh(compound_a)
        session.refresh(compound_b1)
        session.refresh(compound_b2)
        compound_a_id = int(compound_a.id)
        compound_b1_id = int(compound_b1.id)
        compound_b2_id = int(compound_b2.id)

        session.add_all(
            [
                CompoundRGroup(
                    compound_id=compound_a_id,
                    patent_id=patent.id,
                    core_smiles="core-a",
                    core_smarts="*",
                    r_label="R1",
                    r_group="Cl[*:1]",
                ),
                CompoundRGroup(
                    compound_id=compound_b1_id,
                    patent_id=patent.id,
                    core_smiles="core-b",
                    core_smarts="*",
                    r_label="R1",
                    r_group="O[*:1]",
                ),
                CompoundRGroup(
                    compound_id=compound_b2_id,
                    patent_id=patent.id,
                    core_smiles="core-b",
                    core_smarts="*",
                    r_label="R1",
                    r_group="O[*:1]",
                ),
            ]
        )
        session.commit()

    core_service = CoreRecommendationService(
        chemberta_service=FakeChemBertaService(),
        vector_index_service=SearchableFakeVectorIndexService(
            [
                {"image_id": compound_a_id, "distance": 0.0},
                {"image_id": compound_b1_id, "distance": 0.2},
                {"image_id": compound_b2_id, "distance": 0.3},
            ]
        ),
    )
    rgroup_service = RGroupRecommendationService(core_recommendation_service=core_service)
    client.app.dependency_overrides[get_core_recommendation_service] = lambda: core_service
    client.app.dependency_overrides[get_rgroup_recommendation_service] = lambda: rgroup_service

    similar_response = client.post(
        "/recommend/similar-cores",
        json={"core_smiles": "core-a", "k": 2},
    )
    assert similar_response.status_code == 200
    assert similar_response.json() == [
        {
            "core_smiles": "core-a",
            "apply_core_smiles": "core-a",
            "score": 1.0,
            "support_count": 1,
            "reason": "embedding similarity",
        },
        {
            "core_smiles": "core-b",
            "apply_core_smiles": "core-b",
            "score": 0.833333,
            "support_count": 2,
            "reason": "embedding similarity",
        },
    ]

    rgroups_response = client.post(
        "/recommend/rgroups",
        json={"core_smiles": "core-a", "attachment_point": "R1", "k": 3},
    )
    assert rgroups_response.status_code == 200
    assert rgroups_response.json() == [
        {
            "rgroup_smiles": "Cl[*:1]",
            "count": 1,
            "reason": "frequent at R1",
        },
        {
            "rgroup_smiles": "O[*:1]",
            "count": 2,
            "reason": "frequent at R1 on similar core",
        },
    ]


def test_compound_browser_returns_paginated_rows(client, session_factory, configured_settings):
    image_path = configured_settings.upload_dir / "compound.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"png-image")

    with Session(session_factory) as session:
        patent = Patent(
            source_url="https://patents.google.com/patent/US20250042916A1/en",
            patent_slug="US20250042916A1",
        )
        session.add(patent)
        session.commit()
        session.refresh(patent)

        for index in range(3):
            image = CompoundImage(
                patent_id=patent.id,
                image_path=str(image_path),
                page_number=index + 1,
                smiles=f"CCO-{index}",
                canonical_smiles=f"CCO-{index}",
                validation_status="VALID",
                is_compound=True,
                kept_for_series_analysis=index == 0,
            )
            session.add(image)
        session.commit()

    response = client.get("/api/compounds?offset=0&limit=2")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert "compound_id" in body["items"][0]
    assert "patent_id" in body["items"][0]
    assert body["items"][0]["patent_code"] == "US20250042916A1"
    assert "page_number" in body["items"][0]
    assert "canonical_smiles" in body["items"][0]
    assert "validation_status" in body["items"][0]
    assert "kept_for_series_analysis" in body["items"][0]
    assert "murcko_scaffold_smiles" in body["items"][0]
    assert "reduced_core" in body["items"][0]


def test_compound_r_groups_endpoint_returns_child_rows(client, session_factory):
    with Session(session_factory) as session:
        patent = Patent(
            source_url="https://patents.google.com/patent/US20250042916A1/en",
            patent_slug="US20250042916A1",
        )
        session.add(patent)
        session.commit()
        session.refresh(patent)

        image = CompoundImage(
            patent_id=patent.id,
            image_path="compound.png",
            smiles="Clc1ccccc1",
            canonical_smiles="Clc1ccccc1",
            validation_status="VALID",
            is_compound=True,
            core_smiles="c1ccc([*:1])cc1",
            core_smarts="[#6]1:[#6]:[#6]([*:1]):[#6]:[#6]:[#6]:1",
        )
        session.add(image)
        session.commit()
        session.refresh(image)
        compound_id = image.id

        session.add(
            CompoundRGroup(
                compound_id=compound_id,
                patent_id=patent.id,
                core_smiles="c1ccc([*:1])cc1",
                core_smarts="[#6]1:[#6]:[#6]([*:1]):[#6]:[#6]:[#6]:1",
                r_label="R1",
                r_group="Cl[*:1]",
                pipeline_version="rdkit-enrichment-v1",
            )
        )
        session.commit()

    response = client.get(f"/api/compounds/{compound_id}/r-groups")
    assert response.status_code == 200
    body = response.json()
    assert body["compound_id"] == compound_id
    assert len(body["items"]) == 1
    assert body["items"][0]["r_label"] == "R1"
    assert body["items"][0]["r_group"] == "Cl[*:1]"


def test_compound_browser_filters_by_patent_code(client, session_factory, configured_settings):
    image_path = configured_settings.upload_dir / "compound-filter.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"png-image")

    with Session(session_factory) as session:
        patent_a = Patent(
            source_url="https://patents.google.com/patent/US20250042916A1/en",
            patent_slug="US20250042916A1",
        )
        patent_b = Patent(
            source_url="https://patents.google.com/patent/WO2025015269A1/en",
            patent_slug="WO2025015269A1",
        )
        session.add(patent_a)
        session.add(patent_b)
        session.commit()
        session.refresh(patent_a)
        session.refresh(patent_b)

        session.add(CompoundImage(patent_id=patent_a.id, image_path=str(image_path), page_number=1))
        session.add(CompoundImage(patent_id=patent_b.id, image_path=str(image_path), page_number=2))
        session.commit()

    response = client.get("/api/compounds?offset=0&limit=20&patent_code=WO2025015269A1")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["patent_code"] == "WO2025015269A1"


def test_patent_metadata_returns_summary_and_rows(client, session_factory):
    with Session(session_factory) as session:
        processed_patent = Patent(
            source_url="https://patents.google.com/patent/US20250042916A1/en",
            patent_slug="US20250042916A1",
        )
        pending_patent = Patent(
            source_url="https://patents.google.com/patent/WO2025015269A1/en",
            patent_slug="WO2025015269A1",
        )
        session.add(processed_patent)
        session.add(pending_patent)
        session.commit()
        session.refresh(processed_patent)
        session.refresh(pending_patent)

        processed_image = CompoundImage(
            patent_id=processed_patent.id,
            image_path="processed.png",
            smiles="CCO",
            embedding=json.dumps([0.1, 0.2, 0.3]),
        )
        pending_image = CompoundImage(
            patent_id=pending_patent.id,
            image_path="pending.png",
        )
        session.add(processed_image)
        session.add(pending_image)
        session.commit()

        processed_image.processing_status = ProcessingStatus.PROCESSED
        session.add(processed_image)
        session.commit()

    response = client.get("/api/patents/metadata?offset=0&limit=20")
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["total_patents"] == 2
    assert body["summary"]["processed_patents"] == 1
    assert body["summary"]["unprocessed_patents"] == 1
    assert len(body["items"]) == 2
    codes = {item["patent_code"] for item in body["items"]}
    assert {"US20250042916A1", "WO2025015269A1"} == codes


def test_patent_metadata_total_patents_counts_distinct_patents(client, session_factory):
    with Session(session_factory) as session:
        patent = Patent(
            source_url="https://patents.google.com/patent/US20250042916A1/en",
            patent_slug="US20250042916A1",
        )
        session.add(patent)
        session.commit()
        session.refresh(patent)

        session.add(CompoundImage(patent_id=patent.id, image_path="compound-1.png"))
        session.add(CompoundImage(patent_id=patent.id, image_path="compound-2.png"))
        session.add(CompoundImage(patent_id=patent.id, image_path="compound-3.png"))
        session.commit()

    response = client.get("/api/patents/metadata?offset=0&limit=20")
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["total_patents"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["total_compounds"] == 3


def test_patent_codes_returns_all_slugs(client, session_factory):
    with Session(session_factory) as session:
        session.add(Patent(source_url="https://patents.google.com/patent/US20250042916A1/en", patent_slug="US20250042916A1"))
        session.add(Patent(source_url="https://patents.google.com/patent/WO2025015269A1/en", patent_slug="WO2025015269A1"))
        session.commit()

    response = client.get("/api/patents/codes")
    assert response.status_code == 200
    assert response.json() == ["US20250042916A1", "WO2025015269A1"]


def test_reset_database_clears_rows_files_and_faiss(client, session_factory, configured_settings):
    extracted_dir = configured_settings.extracted_image_dir / "US20250042916A1"
    search_dir = configured_settings.search_tmp_dir
    extracted_dir.mkdir(parents=True, exist_ok=True)
    search_dir.mkdir(parents=True, exist_ok=True)
    (extracted_dir / "compound.png").write_bytes(b"png-image")
    (search_dir / "query.png").write_bytes(b"query-image")
    configured_settings.faiss_index_path.parent.mkdir(parents=True, exist_ok=True)
    configured_settings.faiss_index_path.write_bytes(b"index")
    configured_settings.faiss_mapping_path.write_text("[]", encoding="utf-8")

    with Session(session_factory) as session:
        patent = Patent(
            source_url="https://patents.google.com/patent/US20250042916A1/en",
            patent_slug="US20250042916A1",
        )
        session.add(patent)
        session.commit()
        session.refresh(patent)

        session.add(CompoundImage(patent_id=patent.id, image_path=str(extracted_dir / "compound.png")))
        session.commit()

        job = JobRun(job_type="image_processing")
        session.add(job)
        session.commit()
        session.refresh(job)

        session.add(JobLog(job_id=job.id, level="info", message="hello"))
        session.commit()

    response = client.post("/api/admin/reset-database")
    assert response.status_code == 200
    body = response.json()
    assert body["patents_deleted"] == 1
    assert body["compounds_deleted"] == 1
    assert body["jobs_deleted"] == 1
    assert body["logs_deleted"] == 1
    assert body["files_deleted"] == 2

    with Session(session_factory) as session:
        assert session.exec(select(Patent)).all() == []
        assert session.exec(select(CompoundImage)).all() == []
        assert session.exec(select(JobRun)).all() == []
        assert session.exec(select(JobLog)).all() == []

    assert not configured_settings.faiss_index_path.exists()
    assert not configured_settings.faiss_mapping_path.exists()
    assert list(configured_settings.extracted_image_dir.rglob("*")) == []
    assert list(configured_settings.search_tmp_dir.rglob("*")) == []
