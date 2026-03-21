from __future__ import annotations

from sqlalchemy import text
from sqlmodel import Session

from app.core.config import Settings
from app.schemas.health import ComponentHealth, HealthResponse
from app.services.chemberta_service import ChemBertaService
from app.services.extraction_service import ExtractionService
from app.services.smiles_recognition_service import SmilesRecognitionService
from app.services.vector_index_service import VectorIndexService


class HealthService:
    def __init__(
        self,
        *,
        settings: Settings,
        extraction_service: ExtractionService,
        vector_index_service: VectorIndexService,
        smiles_recognition_service: SmilesRecognitionService,
        chemberta_service: ChemBertaService,
    ) -> None:
        self.settings = settings
        self.extraction_service = extraction_service
        self.vector_index_service = vector_index_service
        self.smiles_recognition_service = smiles_recognition_service
        self.chemberta_service = chemberta_service

    def _db_health(self, session: Session) -> ComponentHealth:
        session.exec(text("SELECT 1")).one()
        return ComponentHealth(status="ok", detail="database reachable")

    def _faiss_health(self) -> ComponentHealth:
        meta = {
            "index_path": str(self.settings.faiss_index_path),
            "mapping_path": str(self.settings.faiss_mapping_path),
            "dimension": self.vector_index_service.dimension,
        }
        return ComponentHealth(status="ok", detail="faiss ready", meta=meta)

    def _extractor_health(self) -> ComponentHealth:
        if not self.extraction_service.module_exists():
            return ComponentHealth(
                status="error",
                detail=f"missing extractor at {self.extraction_service.module_path}",
            )
        self.extraction_service.load_module()
        return ComponentHealth(status="ok", detail="extractor importable")

    def _model_health(self) -> dict[str, ComponentHealth]:
        smiles_ready, smiles_detail = self.smiles_recognition_service.is_ready()
        chemberta_ready, chemberta_detail = self.chemberta_service.is_ready()
        return {
            "smiles_recognizer": ComponentHealth(
                status="ok" if smiles_ready else "error",
                detail=smiles_detail,
                meta={
                    "backend": self.smiles_recognition_service.name,
                    "device": self.smiles_recognition_service.device,
                },
            ),
            "chemberta": ComponentHealth(
                status="ok" if chemberta_ready else "error",
                detail=chemberta_detail,
                meta={"device": self.chemberta_service.device},
            ),
        }

    def get_health(self, session: Session) -> HealthResponse:
        components = {
            "database": self._db_health(session),
            "faiss": self._faiss_health(),
            "extractor": self._extractor_health(),
        }
        components.update(self._model_health())
        overall = "ok" if all(item.status == "ok" for item in components.values()) else "degraded"
        return HealthResponse(status=overall, components=components)
