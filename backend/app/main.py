from __future__ import annotations

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.compounds import router as compounds_router
from app.api.health import router as health_router
from app.api.images import router as images_router
from app.api.jobs import router as jobs_router
from app.api.patents import router as patents_router
from app.api.search import router as search_router
from app.core.config import get_settings
from app.core.dependencies import get_vector_index_service
from app.core.logging import configure_logging, get_logger
from app.db.init_db import init_db
from app.db.session import Session, engine
from app.repositories.compound_image_repository import CompoundImageRepository


logger = get_logger(__name__)


def rebuild_faiss_if_needed() -> None:
    repository = CompoundImageRepository()
    vector_index_service = get_vector_index_service()
    try:
        if vector_index_service.load():
            logger.info("Loaded FAISS index from disk")
            return
    except Exception as exc:
        logger.warning("Failed to load FAISS index, rebuilding from database: %s", exc)

    with Session(engine) as session:
        items = []
        for image in repository.list_indexable(session):
            if image.id is None or image.embedding is None:
                continue
            items.append((image.id, json.loads(image.embedding)))
        vector_index_service.rebuild(items)
        logger.info("Rebuilt FAISS index with %s embeddings", len(items))


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    settings = get_settings()
    settings.ensure_directories()
    init_db()
    rebuild_faiss_if_needed()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.api_title, version=settings.api_version, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.mount("/static", StaticFiles(directory=str(settings.upload_dir.resolve())), name="static")
    app.include_router(health_router)
    app.include_router(compounds_router)
    app.include_router(jobs_router)
    app.include_router(patents_router)
    app.include_router(images_router)
    app.include_router(search_router)

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "name": settings.api_title,
            "version": settings.api_version,
            "health": "/api/health",
        }

    return app


app = create_app()
