from __future__ import annotations

from app.core.dependencies import get_molscribe_service, get_smiles_recognition_service
from app.services.molscribe_service import MolScribeService


def test_smiles_recognition_uses_molscribe(configured_settings):
    get_molscribe_service.cache_clear()
    get_smiles_recognition_service.cache_clear()

    service = get_smiles_recognition_service()
    assert isinstance(service, MolScribeService)
    assert service.name == "molscribe"
    assert service.model_path == configured_settings.molscribe_model_path
