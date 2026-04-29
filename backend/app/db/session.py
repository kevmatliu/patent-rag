from __future__ import annotations

from app.models import CompoundCoreCandidate, CompoundCoreCandidateRGroup, CompoundImage, JobLog, JobRun, Patent  # noqa: F401
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


def get_session() -> Session:
    with Session(engine) as session:
        yield session


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
