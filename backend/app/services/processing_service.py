from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from sqlmodel import Session

from app.core.logging import get_logger
from app.repositories.compound_image_repository import CompoundImageRepository
from app.services.chemberta_service import ChemBertaService
from app.services.smiles_recognition_service import SmilesRecognitionService
from app.services.vector_index_service import VectorIndexService


@dataclass
class ProcessingFailure:
    image_id: int
    error: str


@dataclass
class ProcessingResult:
    processed_image_ids: list[int]
    failures: list[ProcessingFailure]
    stopped_early: bool = False


class ProcessingService:
    def __init__(
        self,
        *,
        smiles_recognition_service: SmilesRecognitionService,
        chemberta_service: ChemBertaService,
        vector_index_service: VectorIndexService,
    ) -> None:
        self.smiles_recognition_service = smiles_recognition_service
        self.chemberta_service = chemberta_service
        self.vector_index_service = vector_index_service
        self.compound_repository = CompoundImageRepository()
        self.logger = get_logger(__name__)

    def process_images(
        self,
        session: Session,
        *,
        limit: int,
        order: str,
        patent_codes: Optional[list[str]] = None,
        compound_ids: Optional[list[int]] = None,
        progress_callback: Optional[Callable[[str, str], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> ProcessingResult:
        images = self.compound_repository.list_unprocessed(
            session,
            limit=limit,
            order=order,
            patent_codes=patent_codes,
            compound_ids=compound_ids,
        )
        processed_image_ids: list[int] = []
        failures: list[ProcessingFailure] = []
        stopped_early = False

        if progress_callback is not None:
            progress_callback("info", f"Starting processing job for {len(images)} image(s).")

        for index, image in enumerate(images, start=1):
            if should_stop is not None and should_stop():
                stopped_early = True
                if progress_callback is not None:
                    progress_callback("info", "Processing stop requested. Ending after already completed work.")
                break
            assert image.id is not None
            try:
                if progress_callback is not None:
                    progress_callback("info", f"Image {index}/{len(images)}: starting record #{image.id}.")
                self.compound_repository.mark_processing(session, image)
                if progress_callback is not None:
                    progress_callback(
                        "info",
                        f"Image {index}/{len(images)}: running {self.smiles_recognition_service.name.upper()}.",
                    )
                smiles = self.smiles_recognition_service.image_to_smiles(image.image_path)
                if progress_callback is not None:
                    progress_callback("info", f"Image {index}/{len(images)}: generated SMILES.")
                embedding = self.chemberta_service.smiles_to_embedding(smiles)
                if progress_callback is not None:
                    progress_callback("info", f"Image {index}/{len(images)}: generated ChemBERTa embedding.")
                self.compound_repository.mark_processed(
                    session,
                    image,
                    smiles=smiles,
                    embedding=embedding,
                )
                self.vector_index_service.add_vector(image.id, embedding)
                processed_image_ids.append(image.id)
                if progress_callback is not None:
                    progress_callback("info", f"Image {index}/{len(images)}: indexed in FAISS and marked processed.")
            except Exception as exc:
                self.logger.exception("Processing failed for image %s", image.id)
                self.compound_repository.mark_failed(session, image, error=str(exc))
                failures.append(ProcessingFailure(image_id=image.id, error=str(exc)))
                if progress_callback is not None:
                    progress_callback("error", f"Image {index}/{len(images)} failed for record #{image.id}: {exc}")

        if progress_callback is not None:
            progress_callback(
                "info",
                f"Finished processing job. Processed {len(processed_image_ids)} image(s), failed {len(failures)}.",
            )

        return ProcessingResult(
            processed_image_ids=processed_image_ids,
            failures=failures,
            stopped_early=stopped_early,
        )
