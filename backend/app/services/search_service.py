from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Callable, Optional

from fastapi import UploadFile
from sqlmodel import Session

from app.core.config import Settings
from app.repositories.compound_image_repository import CompoundImageRepository
from app.schemas.image_processing import SearchResultItem, SearchResponse
from app.services.chemberta_service import ChemBertaService
from app.services.smiles_recognition_service import SmilesRecognitionService
from app.services.vector_index_service import VectorIndexService


class SearchService:
    def __init__(
        self,
        *,
        settings: Settings,
        smiles_recognition_service: SmilesRecognitionService,
        chemberta_service: ChemBertaService,
        vector_index_service: VectorIndexService,
    ) -> None:
        self.settings = settings
        self.smiles_recognition_service = smiles_recognition_service
        self.chemberta_service = chemberta_service
        self.vector_index_service = vector_index_service
        self.compound_repository = CompoundImageRepository()

    def _distance_to_similarity(self, distance: float) -> float:
        return round(1.0 / (1.0 + max(distance, 0.0)), 6)

    def search_by_image_path(
        self,
        session: Session,
        *,
        image_path: Path,
        k: int,
        progress_callback: Optional[Callable[[str, str], None]] = None,
    ) -> SearchResponse:
        if progress_callback is not None:
            progress_callback("info", f"Running {self.smiles_recognition_service.name.upper()} on query image.")

        query_smiles = self.smiles_recognition_service.image_to_smiles(str(image_path))
        if progress_callback is not None:
            progress_callback("info", "Generated query SMILES.")

        return self.search_by_smiles(
            session,
            smiles=query_smiles,
            k=k,
            progress_callback=progress_callback,
            query_smiles=query_smiles,
        )

    def search_by_smiles(
        self,
        session: Session,
        *,
        smiles: str,
        k: int,
        progress_callback: Optional[Callable[[str, str], None]] = None,
        query_smiles: Optional[str] = None,
    ) -> SearchResponse:
        query_smiles_value = (query_smiles or smiles).strip()
        query_embedding = self.chemberta_service.smiles_to_embedding(query_smiles_value)
        if progress_callback is not None:
            progress_callback("info", "Generated ChemBERTa embedding for query.")

        raw_results = self.vector_index_service.search(query_embedding, k)
        if progress_callback is not None:
            progress_callback("info", f"FAISS returned {len(raw_results)} match(es).")

        result_ids = [int(item["image_id"]) for item in raw_results]
        hydrated_rows = self.compound_repository.get_search_rows(session, result_ids)
        row_by_id = {row[0].id: row for row in hydrated_rows}

        results: list[SearchResultItem] = []
        for item in raw_results:
            image_id = int(item["image_id"])
            row = row_by_id.get(image_id)
            if row is None:
                continue
            compound_row, patent_row = row
            image_path = Path(compound_row.image_path)
            relative_image = image_path.relative_to(self.settings.upload_dir.resolve())
            image_url = f"/static/{relative_image.as_posix()}"
            results.append(
                SearchResultItem(
                    image_id=image_id,
                    similarity=self._distance_to_similarity(float(item["distance"])),
                    smiles=compound_row.smiles,
                    image_url=image_url,
                    patent_code=patent_row.patent_slug,
                    page_number=compound_row.page_number,
                    patent_source_url=patent_row.source_url,
                )
            )

        if progress_callback is not None:
            progress_callback("info", "Finished search job.")

        return SearchResponse(query_smiles=query_smiles_value, results=results)

    async def search_by_image(self, session: Session, *, upload: UploadFile, k: int) -> SearchResponse:
        suffix = Path(upload.filename or "query.png").suffix or ".png"
        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            dir=self.settings.search_tmp_dir,
            delete=False,
        ) as temp_file:
            temp_file.write(await upload.read())
            temp_path = Path(temp_file.name)

        try:
            return self.search_by_image_path(session, image_path=temp_path, k=k)
        finally:
            temp_path.unlink(missing_ok=True)
