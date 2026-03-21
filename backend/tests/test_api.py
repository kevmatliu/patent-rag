from __future__ import annotations

import json
from pathlib import Path
import time

from app.core.dependencies import (
    get_extraction_service,
    get_patent_fetch_service,
    get_processing_service,
    get_search_service,
)
from app.repositories.job_repository import JobRepository
from app.models.compound_image import CompoundImage
from app.models.enums import ExtractionStatus, ProcessingStatus
from app.models.patent import Patent
from app.repositories.compound_image_repository import CompoundImageRepository
from app.schemas.image_processing import SearchResponse, SearchResultItem
from app.services.patent_fetch_service import PatentFetchResult
from app.services.processing_service import ProcessingService
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


class FakeDecimerService:
    name = "decimer"
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


def test_process_images_updates_rows(client, session_factory, tmp_path):
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
        smiles_recognition_service=FakeDecimerService(),
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
        assert json.loads(stored[0].embedding) == [0.1, 0.2, 0.3]


def test_process_images_job_contains_progress_logs(client, session_factory, tmp_path):
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
        smiles_recognition_service=FakeDecimerService(),
        chemberta_service=FakeChemBertaService(),
        vector_index_service=FakeVectorIndexService(),
    )
    client.app.dependency_overrides[get_processing_service] = lambda: processing_service

    response = client.post("/api/images/process", json={"limit": 5, "order": "oldest"})
    assert response.status_code == 200

    body = wait_for_job(client, response.json()["job_id"])
    assert body["status"] == "completed"
    assert any("running DECIMER" in log["message"] for log in body["logs"])
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


def test_patent_codes_returns_all_slugs(client, session_factory):
    with Session(session_factory) as session:
        session.add(Patent(source_url="https://patents.google.com/patent/US20250042916A1/en", patent_slug="US20250042916A1"))
        session.add(Patent(source_url="https://patents.google.com/patent/WO2025015269A1/en", patent_slug="WO2025015269A1"))
        session.commit()

    response = client.get("/api/patents/codes")
    assert response.status_code == 200
    assert response.json() == ["US20250042916A1", "WO2025015269A1"]
