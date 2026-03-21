from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.patent_fetch_service import PatentFetchService


def test_validate_google_patents_url_accepts_patent_page():
    service = PatentFetchService(get_settings())
    patent_slug = service.validate_google_patents_url(
        "https://patents.google.com/patent/US20250042916A1/en"
    )
    assert patent_slug == "US20250042916A1"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/patent/US20250042916A1/en",
        "ftp://patents.google.com/patent/US20250042916A1/en",
        "https://patents.google.com/search?q=chemistry",
    ],
)
def test_validate_google_patents_url_rejects_invalid_urls(url: str):
    service = PatentFetchService(get_settings())
    with pytest.raises(ValueError):
        service.validate_google_patents_url(url)
