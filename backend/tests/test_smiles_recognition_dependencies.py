from __future__ import annotations

from app.core.dependencies import (
    get_decimer_service,
    get_molscribe_service,
    get_smiles_recognition_service,
)
from app.services.decimer_service import DecimerService
from app.services.molscribe_service import MolScribeService


def test_smiles_recognition_defaults_to_decimer(configured_settings):
    configured_settings.ocr_backend = "decimer"
    get_smiles_recognition_service.cache_clear()
    service = get_smiles_recognition_service()
    assert isinstance(service, DecimerService)
    assert service.name == "decimer"


def test_smiles_recognition_can_switch_to_molscribe(configured_settings):
    configured_settings.ocr_backend = "molscribe"
    get_decimer_service.cache_clear()
    get_molscribe_service.cache_clear()
    get_smiles_recognition_service.cache_clear()

    service = get_smiles_recognition_service()
    assert isinstance(service, MolScribeService)
    assert service.name == "molscribe"
