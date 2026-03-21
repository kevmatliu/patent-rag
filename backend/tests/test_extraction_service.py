from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.services.extraction_service import ExtractionService


def test_extraction_service_loads_dataclass_module(tmp_path, configured_settings):
    module_path = tmp_path / "fake_extractor.py"
    module_path.write_text(
        """
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Payload:
    image_bytes: bytes

def extract_from_patent(url, patent_slug, pdf_bytes):
    return [Payload(image_bytes=b'test')]
""".strip(),
        encoding="utf-8",
    )

    service = ExtractionService(configured_settings)
    service.module_path = module_path

    results = service.extract_from_patent(
        url="https://patents.google.com/patent/US999/en",
        patent_slug="US999",
        pdf_bytes=b"%PDF-1.4",
    )

    assert len(results) == 1
    assert Path(str(results[0]["image_path"])).exists()
    assert results[0]["page_number"] is None


def test_extraction_service_saves_bytes_payloads(tmp_path, configured_settings):
    module_path = tmp_path / "fake_extractor.py"
    module_path.write_text(
        """
def extract_from_patent(url, patent_slug, pdf_bytes):
    return [b'first-image', b'second-image']
""".strip(),
        encoding="utf-8",
    )

    service = ExtractionService(configured_settings)
    service.module_path = module_path

    results = service.extract_from_patent(
        url="https://patents.google.com/patent/US123/en",
        patent_slug="US123",
        pdf_bytes=b"%PDF-1.4",
    )

    assert len(results) == 2
    assert all(Path(str(item["image_path"])).exists() for item in results)
    assert all(item["page_number"] is None for item in results)


def test_extraction_service_copies_image_paths(tmp_path, configured_settings):
    source = tmp_path / "source.png"
    Image.new("RGB", (20, 20), color="white").save(source)

    module_path = tmp_path / "fake_extractor.py"
    module_path.write_text(
        f"""
def extract_from_patent(url, patent_slug, pdf_bytes):
    return [{str(source)!r}]
""".strip(),
        encoding="utf-8",
    )

    service = ExtractionService(configured_settings)
    service.module_path = module_path

    results = service.extract_from_patent(
        url="https://patents.google.com/patent/US456/en",
        patent_slug="US456",
        pdf_bytes=b"%PDF-1.4",
    )

    copied_path = Path(str(results[0]["image_path"]))
    assert copied_path.exists()
    assert copied_path != source
    assert results[0]["page_number"] is None
