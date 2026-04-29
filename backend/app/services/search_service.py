from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Callable, Optional

from fastapi import UploadFile
from sqlmodel import Session

from app.core.config import Settings
from app.models.compound_core_candidate import CompoundCoreCandidate
from app.models.compound_core_candidate_r_group import CompoundCoreCandidateRGroup
from app.models.compound_image import CompoundImage
from app.repositories.compound_image_repository import CompoundImageRepository
from app.repositories.compound_core_candidate_repository import CompoundCoreCandidateRepository
from app.schemas.image_processing import SearchResultItem, SearchResponse
from app.services.chemberta_service import ChemBertaService
from app.services.smiles_recognition_service import SmilesRecognitionService
from app.services.vector_index_service import VectorIndexService

from sqlalchemy.orm import aliased
from sqlmodel import select
import numpy as np
from rdkit import Chem
from app.services.scaffold_analysis import analyze_scaffolds, ScaffoldInput


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
        self.core_candidate_repository = CompoundCoreCandidateRepository()

    def _distance_to_similarity(self, distance: float) -> float:
        return round(1.0 / (1.0 + max(distance, 0.0)), 6)

    def search_by_image_path(
        self,
        session: Session,
        *,
        image_path: Path,
        k: int,
        patent_codes: Optional[list[str]] = None,
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
            patent_codes=patent_codes,
            progress_callback=progress_callback,
            query_smiles=query_smiles,
        )

    def search_by_smiles(
        self,
        session: Session,
        *,
        smiles: str,
        k: int,
        patent_codes: Optional[list[str]] = None,
        progress_callback: Optional[Callable[[str, str], None]] = None,
        query_smiles: Optional[str] = None,
    ) -> SearchResponse:
        query_smiles_value = (query_smiles or smiles).strip()
        query_embedding = self.chemberta_service.smiles_to_embedding(query_smiles_value)
        if progress_callback is not None:
            progress_callback("info", "Generated ChemBERTa embedding for query.")

        query_k = 5000 if patent_codes else k
        raw_results = self.vector_index_service.search(query_embedding, query_k)
        if progress_callback is not None:
            progress_callback("info", f"FAISS returned {len(raw_results)} match(es).")

        result_ids = [int(item["image_id"]) for item in raw_results]
        hydrated_rows = self.compound_repository.get_search_rows(session, result_ids)
        row_by_id = {row[0].id: row for row in hydrated_rows}

        results: list[SearchResultItem] = []
        valid_patent_codes = set(patent_codes) if patent_codes else None
        
        for item in raw_results:
            if len(results) >= k:
                break
                
            image_id = int(item["image_id"])
            row = row_by_id.get(image_id)
            if row is None:
                continue
            compound_row, patent_row = row
            
            if valid_patent_codes and patent_row.patent_slug not in valid_patent_codes:
                continue
                
            image_path = Path(compound_row.image_path)
            relative_image = image_path.relative_to(self.settings.upload_dir.resolve())
            image_url = f"/static/{relative_image.as_posix()}"
            results.append(
                SearchResultItem(
                    image_id=image_id,
                    similarity=self._distance_to_similarity(float(item["distance"])),
                    smiles=compound_row.canonical_smiles or compound_row.smiles,
                    image_url=image_url,
                    patent_code=patent_row.patent_slug,
                    page_number=compound_row.page_number,
                    patent_source_url=patent_row.source_url,
                )
            )

        if progress_callback is not None:
            progress_callback("info", "Finished search job.")

        query_x, query_y = None, None
        try:
            from app.api.compounds import MAP_PROJECTION_CACHE
            if MAP_PROJECTION_CACHE["components"] is not None and MAP_PROJECTION_CACHE["mean"] is not None:
                matrix = np.array([query_embedding], dtype=np.float32)
                centered = matrix - MAP_PROJECTION_CACHE["mean"]
                projected = centered @ MAP_PROJECTION_CACHE["components"]
                if projected.shape[1] == 1:
                    projected = np.column_stack([projected[:, 0], np.zeros(projected.shape[0], dtype=np.float32)])
                normalized = (projected - MAP_PROJECTION_CACHE["mins"]) / MAP_PROJECTION_CACHE["spans"]
                query_x, query_y = float(normalized[0, 0]), float(normalized[0, 1])
        except Exception:
            pass

        return SearchResponse(query_smiles=query_smiles_value, query_x=query_x, query_y=query_y, results=results)

    async def search_by_image(self, session: Session, *, upload: UploadFile, k: int, patent_codes: Optional[list[str]] = None) -> SearchResponse:
        suffix = Path(upload.filename or "query.png").suffix or ".png"
        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            dir=self.settings.search_tmp_dir,
            delete=False,
        ) as temp_file:
            temp_file.write(await upload.read())
            temp_path = Path(temp_file.name)

        try:
            return self.search_by_image_path(session, image_path=temp_path, k=k, patent_codes=patent_codes)
        finally:
            temp_path.unlink(missing_ok=True)

    def search_by_structure(
        self,
        session: Session,
        *,
        core_smiles: Optional[str],
        r_groups: dict[str, str],
        k: int,
        progress_callback: Optional[Callable[[str, str], None]] = None,
    ) -> SearchResponse:
        # 1. Filter by R-groups exactly
        statement = select(CompoundImage.id).distinct()
        active_r_groups = {label: sm.strip() for label, sm in r_groups.items() if sm and sm.strip()}
        
        for label, r_smiles in active_r_groups.items():
            alias = aliased(CompoundCoreCandidateRGroup)
            statement = statement.join(alias, alias.compound_id == CompoundImage.id)
            statement = statement.where(alias.r_label == label, alias.r_group_smiles == r_smiles)
        
        matched_ids = list(session.exec(statement).all())
        if not matched_ids:
            return SearchResponse(query_smiles=core_smiles or "N/A", results=[])

        if progress_callback:
            progress_callback("info", f"Found {len(matched_ids)} compound(s) matching R-group constraints.")

        # 2. Rank by core similarity if query exists
        if not core_smiles or not core_smiles.strip():
            top_ids = matched_ids[:k]
            # Similarity is 1.0 since no core constraint
            id_similarity_map = {image_id: 1.0 for image_id in top_ids}
        else:
            query_smiles_str = core_smiles.strip()
            # 1. Standardize query Core to its Reduced Core
            query_mol = Chem.MolFromSmiles(query_smiles_str)
            if query_mol:
                try:
                    analysis = analyze_scaffolds([ScaffoldInput(compound_id=0, mol=query_mol)])
                    query_reduced_core = analysis[0].reduced_core or query_smiles_str
                except Exception:
                    query_reduced_core = query_smiles_str
            else:
                query_reduced_core = query_smiles_str

            query_embedding = self.chemberta_service.smiles_to_embedding(query_reduced_core)
            query_vec = np.array(query_embedding).astype("float32")
            norm = np.linalg.norm(query_vec)
            if norm > 0:
                query_vec /= norm

            # 2. Get Reduced Cores for all candidates
            preferred_candidates = self.core_candidate_repository.get_preferred_by_compound_ids(session, matched_ids)

            scored: list[tuple[int, float]] = []
            for image_id in matched_ids:
                candidate = preferred_candidates.get(image_id)
                # Use the reduced_core from DB, or fallback to full compound analysis if not present
                target_core = (candidate.reduced_core if candidate else "") or ""
                
                # We need embeddings for these cores. 
                # Calculating on the fly is acceptable for small result sets.
                if not target_core:
                    # Fallback or skip
                    scored.append((image_id, 0.0))
                    continue
                
                cand_embedding = self.chemberta_service.smiles_to_embedding(target_core)
                cand_vec = np.array(cand_embedding).astype("float32")
                c_norm = np.linalg.norm(cand_vec)
                if c_norm > 0:
                    cand_vec /= c_norm
                
                distance = np.linalg.norm(query_vec - cand_vec)
                similarity = self._distance_to_similarity(float(distance))
                scored.append((image_id, similarity))
            
            scored.sort(key=lambda x: x[1], reverse=True)
            top_ids = [x[0] for x in scored[:k]]
            id_similarity_map = {x[0]: x[1] for x in scored[:k]}

        # 3. Hydrate results
        hydrated_rows = self.compound_repository.get_search_rows(session, top_ids)
        row_by_id = {row[0].id: row for row in hydrated_rows}

        results: list[SearchResultItem] = []
        for image_id in top_ids:
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
                    similarity=id_similarity_map.get(image_id, 0.0),
                    smiles=compound_row.canonical_smiles or compound_row.smiles,
                    image_url=image_url,
                    patent_code=patent_row.patent_slug,
                    page_number=compound_row.page_number,
                    patent_source_url=patent_row.source_url,
                )
            )

        if progress_callback:
            progress_callback("info", f"Finished structure search with {len(results)} results.")

        return SearchResponse(query_smiles=core_smiles or "Core-agnostic (R-group filtered)", results=results)
