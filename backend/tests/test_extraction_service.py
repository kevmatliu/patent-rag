from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.services.extraction_service import CompoundOccurrence, ExtractionService


def test_extraction_service_load_module_checks_dependencies(configured_settings):
    service = ExtractionService(configured_settings)

    loaded = service.load_module()

    assert loaded is service


def test_extraction_service_saves_dataclass_payloads(tmp_path, configured_settings):
    service = ExtractionService(configured_settings)
    payload = CompoundOccurrence(
        compound_number=None,
        page=3,
        image_bytes=b"test",
        bbox=(1, 2, 3, 4),
    )

    image_path = service._save_payload(payload, tmp_path, 1)

    assert Path(image_path).exists()
    assert service._extract_page_number(payload) == 3


def test_extraction_service_saves_bytes_payloads(tmp_path, configured_settings):
    service = ExtractionService(configured_settings)

    first_path = Path(service._save_payload(b"first-image", tmp_path, 1))
    second_path = Path(service._save_payload(b"second-image", tmp_path, 2))

    assert first_path.exists()
    assert second_path.exists()


def test_extraction_service_copies_image_paths(tmp_path, configured_settings):
    source = tmp_path / "source.png"
    Image.new("RGB", (20, 20), color="white").save(source)
    service = ExtractionService(configured_settings)

    copied_path = Path(service._save_payload(str(source), tmp_path / "copied", 1))

    assert copied_path.exists()
    assert copied_path != source
