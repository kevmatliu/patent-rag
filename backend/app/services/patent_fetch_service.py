from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

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
        self.headers = {"User-Agent": "Mozilla/5.0 (PatentRAGChemV2/1.0)"}

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
        page_response = requests.get(url, headers=self.headers, timeout=60)
        page_response.raise_for_status()

        soup = BeautifulSoup(page_response.text, "html.parser")
        pdf_url = None
        citation = soup.find("meta", {"name": "citation_pdf_url"})
        if citation and citation.get("content"):
            pdf_url = citation["content"]

        if not pdf_url:
            raise RuntimeError(f"Could not locate a PDF link for patent {patent_slug}")

        pdf_response = requests.get(pdf_url, headers=self.headers, timeout=120)
        pdf_response.raise_for_status()
        if "application/pdf" not in pdf_response.headers.get("content-type", "").lower():
            raise RuntimeError("Fetched patent asset is not a PDF")

        return PatentFetchResult(
            source_url=url.strip(),
            patent_slug=patent_slug,
            pdf_bytes=pdf_response.content,
        )
