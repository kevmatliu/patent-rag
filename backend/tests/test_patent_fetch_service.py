from __future__ import annotations

import pytest
import requests

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


class FakeResponse:
    def __init__(self, *, status_code: int, text: str = "", content: bytes = b"", headers: dict[str, str] | None = None, url: str = "https://example.com", reason: str = "OK") -> None:
        self.status_code = status_code
        self.text = text
        self.content = content
        self.headers = headers or {}
        self.url = url
        self.reason = reason

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(
                f"{self.status_code} Server Error: {self.reason} for url: {self.url}",
                response=self,
            )


def test_fetch_retries_transient_503_and_downloads_pdf(monkeypatch):
    service = PatentFetchService(get_settings())
    calls: list[str] = []
    html = """
    <html>
      <head>
        <meta name="citation_pdf_url" content="https://patentimages.storage.googleapis.com/fake/test.pdf" />
      </head>
    </html>
    """

    def fake_get(url: str, *, headers, timeout):
        calls.append(url)
        if len(calls) == 1:
            return FakeResponse(status_code=503, url=url, reason="Service Unavailable")
        if url.endswith("/en"):
            return FakeResponse(status_code=200, text=html, headers={"content-type": "text/html"}, url=url)
        return FakeResponse(
            status_code=200,
            content=b"%PDF-1.4 fake",
            headers={"content-type": "application/pdf"},
            url=url,
        )

    monkeypatch.setattr(service.session, "get", fake_get)
    monkeypatch.setattr("app.services.patent_fetch_service.time.sleep", lambda _: None)

    result = service.fetch("https://patents.google.com/patent/US20250042916A1/en")

    assert result.patent_slug == "US20250042916A1"
    assert result.pdf_bytes == b"%PDF-1.4 fake"
    assert calls == [
        "https://patents.google.com/patent/US20250042916A1/en",
        "https://patents.google.com/patent/US20250042916A1/en",
        "https://patentimages.storage.googleapis.com/fake/test.pdf",
    ]


def test_fetch_falls_back_to_download_anchor_when_meta_tag_missing(monkeypatch):
    service = PatentFetchService(get_settings())
    html = """
    <html>
      <body>
        <a href="https://patentimages.storage.googleapis.com/fake/test.pdf">Download PDF</a>
      </body>
    </html>
    """

    def fake_get(url: str, *, headers, timeout):
        if url.endswith("/en"):
            return FakeResponse(status_code=200, text=html, headers={"content-type": "text/html"}, url=url)
        return FakeResponse(
            status_code=200,
            content=b"%PDF-1.4 fake",
            headers={"content-type": "application/pdf"},
            url=url,
        )

    monkeypatch.setattr(service.session, "get", fake_get)

    result = service.fetch("https://patents.google.com/patent/US20250042916A1/en")

    assert result.pdf_bytes == b"%PDF-1.4 fake"


def test_fetch_raises_clear_error_after_retries(monkeypatch):
    service = PatentFetchService(get_settings())

    def fake_get(url: str, *, headers, timeout):
        return FakeResponse(status_code=503, url=url, reason="Service Unavailable")

    monkeypatch.setattr(service.session, "get", fake_get)
    monkeypatch.setattr("app.services.patent_fetch_service.time.sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="Failed to fetch patent page after 3 attempts"):
        service.fetch("https://patents.google.com/patent/US20250042916A1/en")
