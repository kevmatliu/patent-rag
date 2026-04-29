from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

from sqlmodel import Session

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.compound_core_candidate import CompoundCoreCandidate
from app.models.compound_core_candidate_r_group import CompoundCoreCandidateRGroup
from app.models.compound_image import CompoundImage
from app.models.enums import ProcessingStatus, ValidationStatus
from app.repositories.compound_image_repository import CompoundImageRepository
from app.repositories.compound_core_candidate_repository import CompoundCoreCandidateRepository
from app.repositories.compound_core_candidate_r_group_repository import CompoundCoreCandidateRGroupRepository
from app.services.chemberta_service import ChemBertaService
from app.services.rgroup_decomposition import RGroupInput, decompose_r_groups
from app.services.scaffold_analysis import ScaffoldInput, analyze_scaffolds
from app.services.smiles_recognition_service import SmilesRecognitionService
from app.services.smiles_validation import validate_and_standardize_smiles
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
        self.core_candidate_repository = CompoundCoreCandidateRepository()
        self.r_group_repository = CompoundCoreCandidateRGroupRepository()
        self.logger = get_logger(__name__)
        self.pipeline_version = settings.processing_pipeline_version

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
        targets = self.compound_repository.list_unprocessed(
            session,
            limit=limit,
            order=order,
            patent_codes=patent_codes,
            compound_ids=compound_ids,
        )
        target_ids_by_patent: dict[int, set[int]] = {}
        patent_order: list[int] = []
        for image in targets:
            assert image.id is not None
            if image.patent_id not in target_ids_by_patent:
                patent_order.append(image.patent_id)
                target_ids_by_patent[image.patent_id] = set()
            target_ids_by_patent[image.patent_id].add(image.id)

        processed_image_ids: list[int] = []
        failures: list[ProcessingFailure] = []
        stopped_early = False

        if progress_callback is not None:
            progress_callback(
                "info",
                f"Starting processing job for {len(targets)} image(s) across {len(patent_order)} patent(s).",
            )

        for patent_index, patent_id in enumerate(patent_order, start=1):
            if should_stop is not None and should_stop():
                stopped_early = True
                if progress_callback is not None:
                    progress_callback("info", "Processing stop requested. Ending after already completed work.")
                break

            patent_images = self.compound_repository.list_by_patent(session, patent_id)
            try:
                patent_processed, patent_failures = self._process_patent(
                    session,
                    patent_images=patent_images,
                    target_image_ids=target_ids_by_patent[patent_id],
                    patent_index=patent_index,
                    patent_count=len(patent_order),
                    progress_callback=progress_callback,
                )
            except Exception as exc:
                self.logger.exception("Patent-level processing failed for patent %s", patent_id)
                patent_processed, patent_failures = self._mark_patent_failure(
                    session,
                    patent_images=patent_images,
                    target_image_ids=target_ids_by_patent[patent_id],
                    error=str(exc),
                )
                if progress_callback is not None:
                    progress_callback(
                        "error",
                        f"Patent {patent_index}/{len(patent_order)} failed for patent #{patent_id}: {exc}",
                    )
            processed_image_ids.extend(patent_processed)
            failures.extend(patent_failures)

        self._rebuild_vector_index(session, progress_callback=progress_callback)

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

    def _process_patent(
        self,
        session: Session,
        *,
        patent_images: list[CompoundImage],
        target_image_ids: set[int],
        patent_index: int,
        patent_count: int,
        progress_callback: Optional[Callable[[str, str], None]],
    ) -> tuple[list[int], list[ProcessingFailure]]:
        if not patent_images:
            return [], []

        patent_id = patent_images[0].patent_id
        processed_target_ids: set[int] = set()
        failures: list[ProcessingFailure] = []
        mols_by_compound_id: dict[int, object] = {}

        if progress_callback is not None:
            progress_callback(
                "info",
                f"Patent {patent_index}/{patent_count}: starting patent #{patent_id} with {len(patent_images)} compound image(s).",
            )

        self.r_group_repository.delete_by_patent(session, patent_id)
        self.core_candidate_repository.delete_by_patent(session, patent_id)

        for image in patent_images:
            if image.id is None:
                continue
            targeted = image.id in target_image_ids
            if targeted:
                image.processing_status = ProcessingStatus.PROCESSING
                image.last_error = None
                image.updated_at = datetime.now(timezone.utc)

            smiles_value = image.smiles
            if targeted and not smiles_value:
                try:
                    if progress_callback is not None:
                        progress_callback(
                            "info",
                            f"Patent {patent_index}/{patent_count}: running {self.smiles_recognition_service.name.upper()} for record #{image.id}.",
                        )
                    smiles_value = self.smiles_recognition_service.image_to_smiles(image.image_path)
                    image.smiles = smiles_value
                except Exception as exc:
                    self.logger.exception("MolScribe failed for image %s", image.id)
                    self._mark_pipeline_failure(image, error=str(exc))
                    failures.append(ProcessingFailure(image_id=image.id, error=str(exc)))
                    continue

            if smiles_value is None and image.validation_status == ValidationStatus.UNPROCESSED:
                continue

            validation = validate_and_standardize_smiles(smiles_value)
            self._apply_validation(image, validation_status=validation.status, is_compound=validation.is_compound, canonical_smiles=validation.canonical_smiles, validation_error=validation.error)
            if validation.status == ValidationStatus.VALID and validation.mol is not None:
                mols_by_compound_id[image.id] = validation.mol
            if targeted:
                processed_target_ids.add(image.id)

        kept_valid_images = self._apply_deduplication(patent_images, mols_by_compound_id)

        scaffold_assignments = analyze_scaffolds(
            [ScaffoldInput(compound_id=item.id, mol=mols_by_compound_id[item.id]) for item in kept_valid_images if item.id is not None]
        )
        reduced_core_series: dict[str, list[RGroupInput]] = {}
        assignment_by_compound_id: dict[int, object] = {}
        for image in kept_valid_images:
            if image.id is None:
                continue
            assignment = scaffold_assignments[image.id]
            assignment_by_compound_id[image.id] = assignment
            reduced_core = assignment.reduced_core
            if not reduced_core:
                continue
            series_inputs = reduced_core_series.setdefault(reduced_core, [])
            series_inputs.append(
                RGroupInput(
                    compound_id=image.id,
                    patent_id=image.patent_id,
                    mol=mols_by_compound_id[image.id],
                )
            )

        core_candidate_rows: list[CompoundCoreCandidate] = []
        pending_r_group_rows: list[tuple[int, CompoundCoreCandidateRGroup]] = []
        for reduced_core, series_inputs in reduced_core_series.items():
            decomposition_result = decompose_r_groups(
                core_smiles=reduced_core,
                compounds=series_inputs,
            )
            matched_ids = set(decomposition_result.core_smiles_by_compound)
            for series_input in series_inputs:
                if series_input.compound_id not in matched_ids:
                    continue
                assignment = assignment_by_compound_id.get(series_input.compound_id)
                if assignment is None:
                    continue
                core_candidate_rows.append(
                    CompoundCoreCandidate(
                        compound_id=series_input.compound_id,
                        patent_id=series_input.patent_id,
                        candidate_rank=1,
                        is_selected=True,
                        core_smiles=decomposition_result.core_smiles_by_compound.get(series_input.compound_id),
                        core_smarts=decomposition_result.core_smarts_by_compound.get(series_input.compound_id),
                        reduced_core=assignment.reduced_core,
                        murcko_scaffold_smiles=assignment.murcko_scaffold_smiles,
                        generation_method="rdkit_r_group_decomposition",
                        pipeline_version=self.pipeline_version,
                    )
                )
            for row in decomposition_result.r_groups:
                pending_r_group_rows.append(
                    (
                        row.compound_id,
                        CompoundCoreCandidateRGroup(
                            core_candidate_id=0,
                            compound_id=row.compound_id,
                            patent_id=row.patent_id,
                            r_label=row.r_label,
                            r_group_smiles=row.r_group,
                            attachment_index=row.attachment_index,
                            pipeline_version=self.pipeline_version,
                        ),
                    )
                )

        self.core_candidate_repository.create_many(session, core_candidate_rows)
        session.flush()

        candidate_by_compound_id = {
            candidate.compound_id: candidate
            for candidate in core_candidate_rows
            if candidate.id is not None
        }
        r_group_rows: list[CompoundCoreCandidateRGroup] = []
        for compound_id, row in pending_r_group_rows:
            candidate = candidate_by_compound_id.get(compound_id)
            if candidate is None or candidate.id is None:
                continue
            row.core_candidate_id = candidate.id
            r_group_rows.append(row)

        self.r_group_repository.create_many(session, r_group_rows)

        for image in patent_images:
            if image.id is None:
                continue
            should_embed = (
                image.validation_status == ValidationStatus.VALID
                and image.kept_for_series_analysis
                and not image.is_duplicate_within_patent
            )
            if not should_embed:
                image.embedding = None
                continue

            embedding_input = image.canonical_smiles or image.smiles
            if embedding_input is None:
                image.embedding = None
                continue
            try:
                embedding = self.chemberta_service.smiles_to_embedding(embedding_input)
                image.embedding = json.dumps(embedding)
                image.processing_status = ProcessingStatus.PROCESSED
                image.last_error = None
                image.pipeline_version = self.pipeline_version
                image.updated_at = datetime.now(timezone.utc)
            except Exception as exc:
                self.logger.exception("ChemBERTa embedding failed for image %s", image.id)
                self._mark_pipeline_failure(image, error=str(exc))
                if image.id in processed_target_ids:
                    processed_target_ids.remove(image.id)
                failures.append(ProcessingFailure(image_id=image.id, error=str(exc)))

        session.commit()

        if progress_callback is not None:
            progress_callback(
                "info",
                f"Patent {patent_index}/{patent_count}: finished patent #{patent_id}.",
            )

        return sorted(processed_target_ids), failures

    def _apply_validation(
        self,
        image: CompoundImage,
        *,
        validation_status: ValidationStatus,
        is_compound: Optional[bool],
        canonical_smiles: Optional[str],
        validation_error: Optional[str],
    ) -> None:
        image.validation_status = validation_status
        image.is_compound = is_compound
        image.canonical_smiles = canonical_smiles
        image.validation_error = validation_error
        image.pipeline_version = self.pipeline_version
        image.updated_at = datetime.now(timezone.utc)

        if validation_status == ValidationStatus.VALID:
            image.processing_status = ProcessingStatus.PROCESSED
            image.last_error = None
            return

        image.processing_status = ProcessingStatus.PROCESSED
        image.embedding = None
        image.is_duplicate_within_patent = False
        image.duplicate_of_compound_id = None
        image.kept_for_series_analysis = False
        image.last_error = None

    def _apply_deduplication(
        self,
        patent_images: list[CompoundImage],
        mols_by_compound_id: dict[int, object],
    ) -> list[CompoundImage]:
        seen_canonical_smiles: dict[str, int] = {}
        kept_valid_images: list[CompoundImage] = []
        for image in patent_images:
            if image.id is None or image.validation_status != ValidationStatus.VALID or not image.canonical_smiles:
                continue

            duplicate_of_compound_id = seen_canonical_smiles.get(image.canonical_smiles)
            if duplicate_of_compound_id is None:
                seen_canonical_smiles[image.canonical_smiles] = image.id
                image.is_duplicate_within_patent = False
                image.duplicate_of_compound_id = None
                image.kept_for_series_analysis = True
                kept_valid_images.append(image)
            else:
                image.is_duplicate_within_patent = True
                image.duplicate_of_compound_id = duplicate_of_compound_id
                image.kept_for_series_analysis = False
                image.embedding = None
                image.updated_at = datetime.now(timezone.utc)
                mols_by_compound_id.pop(image.id, None)

        return kept_valid_images

    def _mark_pipeline_failure(self, image: CompoundImage, *, error: str) -> None:
        image.processing_status = ProcessingStatus.FAILED
        image.last_error = error
        image.embedding = None
        image.pipeline_version = self.pipeline_version
        image.updated_at = datetime.now(timezone.utc)

    def _rebuild_vector_index(
        self,
        session: Session,
        *,
        progress_callback: Optional[Callable[[str, str], None]],
    ) -> None:
        items = []
        for image in self.compound_repository.list_indexable(session):
            if image.id is None or image.embedding is None:
                continue
            items.append((image.id, json.loads(image.embedding)))
        self.vector_index_service.rebuild(items)
        if progress_callback is not None:
            progress_callback("info", f"Rebuilt FAISS index with {len(items)} embedding(s).")

    def _mark_patent_failure(
        self,
        session: Session,
        *,
        patent_images: list[CompoundImage],
        target_image_ids: set[int],
        error: str,
    ) -> tuple[list[int], list[ProcessingFailure]]:
        failures: list[ProcessingFailure] = []
        for image in patent_images:
            if image.id is None or image.id not in target_image_ids:
                continue
            self._mark_pipeline_failure(image, error=error)
            failures.append(ProcessingFailure(image_id=image.id, error=error))
        session.commit()
        return [], failures
