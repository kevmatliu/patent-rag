from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.api import images as images_api
from app.api import patents as patents_api
from app.api import search as search_api
from app.core.config import get_settings
from app.core.dependencies import (
    get_chemberta_service,
    get_extraction_service,
    get_health_service,
    get_molscribe_service,
    get_patent_fetch_service,
    get_processing_service,
    get_search_service,
    get_smiles_recognition_service,
    get_vector_index_service,
)
from app.db.session import get_session
from app.main import app


@pytest.fixture
def configured_settings(tmp_path: Path):
    settings = get_settings()
    settings.database_url = f"sqlite:///{tmp_path / 'test.db'}"
    settings.faiss_index_path = tmp_path / "faiss_index" / "index.bin"
    settings.faiss_mapping_path = tmp_path / "faiss_index" / "mapping.json"
    settings.upload_dir = tmp_path / "uploads"
    settings.extracted_image_dir = settings.upload_dir / "extracted"
    settings.search_tmp_dir = settings.upload_dir / "search_tmp"
    settings.molscribe_model_path = tmp_path / "models" / "molscribe" / "model.pth"
    settings.chemberta_model_path = tmp_path / "models" / "chemberta"
    settings.ensure_directories()

    for cache in (
        get_extraction_service,
        get_molscribe_service,
        get_smiles_recognition_service,
        get_chemberta_service,
        get_vector_index_service,
        get_processing_service,
        get_search_service,
        get_health_service,
    ):
        cache.cache_clear()

    return settings


@pytest.fixture
def session_factory(configured_settings):
    engine = create_engine(
        configured_settings.database_url,
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    patents_api.engine = engine
    images_api.engine = engine
    search_api.engine = engine
    return engine


@pytest.fixture
def client(session_factory):
    def override_session():
        with Session(session_factory) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
