from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.services.chemberta_service import ChemBertaService
from app.services.core_recommendation_service import CoreRecommendationService
from app.services.extraction_service import ExtractionService
from app.services.health_service import HealthService
from app.services.molscribe_service import MolScribeService
from app.services.molecule_modification_service import MoleculeModificationService
from app.services.patent_fetch_service import PatentFetchService
from app.services.processing_service import ProcessingService
from app.services.rgroup_recommendation_service import RGroupRecommendationService
from app.services.search_service import SearchService
from app.services.smiles_recognition_service import SmilesRecognitionService
from app.services.vector_index_service import VectorIndexService


def get_patent_fetch_service() -> PatentFetchService:
    return PatentFetchService(get_settings())


@lru_cache(maxsize=1)
def get_extraction_service() -> ExtractionService:
    return ExtractionService(get_settings())


@lru_cache(maxsize=1)
def get_molscribe_service() -> MolScribeService:
    settings: Settings = get_settings()
    return MolScribeService(
        model_path=settings.molscribe_model_path,
        device=settings.model_device,
    )


@lru_cache(maxsize=1)
def get_smiles_recognition_service() -> SmilesRecognitionService:
    return get_molscribe_service()


@lru_cache(maxsize=1)
def get_chemberta_service() -> ChemBertaService:
    settings: Settings = get_settings()
    return ChemBertaService(
        model_path=settings.chemberta_model_path,
        device=settings.model_device,
    )


@lru_cache(maxsize=1)
def get_vector_index_service() -> VectorIndexService:
    settings: Settings = get_settings()
    return VectorIndexService(
        index_path=settings.faiss_index_path,
        mapping_path=settings.faiss_mapping_path,
    )


@lru_cache(maxsize=1)
def get_processing_service() -> ProcessingService:
    return ProcessingService(
        settings=get_settings(),
        smiles_recognition_service=get_smiles_recognition_service(),
        chemberta_service=get_chemberta_service(),
        vector_index_service=get_vector_index_service(),
    )


@lru_cache(maxsize=1)
def get_search_service() -> SearchService:
    return SearchService(
        settings=get_settings(),
        smiles_recognition_service=get_smiles_recognition_service(),
        chemberta_service=get_chemberta_service(),
        vector_index_service=get_vector_index_service(),
    )


@lru_cache(maxsize=1)
def get_core_recommendation_service() -> CoreRecommendationService:
    return CoreRecommendationService(
        chemberta_service=get_chemberta_service(),
        vector_index_service=get_vector_index_service(),
    )


@lru_cache(maxsize=1)
def get_rgroup_recommendation_service() -> RGroupRecommendationService:
    return RGroupRecommendationService(
        core_recommendation_service=get_core_recommendation_service(),
    )


@lru_cache(maxsize=1)
def get_molecule_modification_service() -> MoleculeModificationService:
    return MoleculeModificationService()


@lru_cache(maxsize=1)
def get_health_service() -> HealthService:
    return HealthService(
        settings=get_settings(),
        extraction_service=get_extraction_service(),
        vector_index_service=get_vector_index_service(),
        smiles_recognition_service=get_smiles_recognition_service(),
        chemberta_service=get_chemberta_service(),
    )
