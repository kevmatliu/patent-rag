from __future__ import annotations

import re
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.core.config import Settings


PATENT_PATH_RE = re.compile(r"^/patent/([^/]+)")


@dataclass
class PatentFetchResult:
    source_url: str
    patent_slug: str
    pdf_bytes: bytes


class PatentFetchService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.headers = {
            "User-Agent": "Mozilla/5.0 (PatentRAGChemV2/1.0)",
            "Accept-Language": "en-US,en;q=0.9",
        }
        self.retry_status_codes = {429, 500, 502, 503, 504}
        self.max_attempts = 3
        self.session = requests.Session()

    def _get_with_retries(self, url: str, *, timeout: int, resource_label: str) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self.session.get(url, headers=self.headers, timeout=timeout)
                if response.status_code not in self.retry_status_codes:
                    response.raise_for_status()
                    return response
                last_error = requests.HTTPError(
                    f"{response.status_code} Server Error: {response.reason} for url: {response.url}",
                    response=response,
                )
            except requests.RequestException as exc:
                last_error = exc

            if attempt < self.max_attempts:
                time.sleep(min(2 ** (attempt - 1), 4))

        assert last_error is not None
        raise RuntimeError(f"Failed to fetch patent {resource_label} after {self.max_attempts} attempts: {last_error}") from last_error

    def _extract_pdf_url(self, page_url: str, html: str) -> str | None:
        soup = BeautifulSoup(html, "html.parser")
        citation = soup.find("meta", {"name": "citation_pdf_url"})
        if citation and citation.get("content"):
            return str(citation["content"])

        for anchor in soup.find_all("a", href=True):
            anchor_text = anchor.get_text(" ", strip=True).lower()
            href = str(anchor["href"]).strip()
            if "download pdf" in anchor_text or href.lower().endswith(".pdf"):
                return urljoin(page_url, href)
        return None

    def validate_google_patents_url(self, url: str) -> str:
        parsed = urlparse(url.strip())
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Patent URL must start with http:// or https://")
        if parsed.netloc not in {"patents.google.com", "www.patents.google.com"}:
            raise ValueError("Only Google Patents URLs are supported")
        match = PATENT_PATH_RE.match(parsed.path)
        if not match:
            raise ValueError("Could not extract a patent identifier from the Google Patents URL")
        return match.group(1)

    def fetch(self, url: str) -> PatentFetchResult:
        patent_slug = self.validate_google_patents_url(url)
        page_response = self._get_with_retries(url, timeout=60, resource_label="page")
        pdf_url = self._extract_pdf_url(url.strip(), page_response.text)

        if not pdf_url:
            raise RuntimeError(f"Could not locate a PDF link for patent {patent_slug}")

        pdf_response = self._get_with_retries(pdf_url, timeout=120, resource_label="PDF")
        if "application/pdf" not in pdf_response.headers.get("content-type", "").lower():
            raise RuntimeError("Fetched patent asset is not a PDF")

        return PatentFetchResult(
            source_url=url.strip(),
            patent_slug=patent_slug,
            pdf_bytes=pdf_response.content,
        )
