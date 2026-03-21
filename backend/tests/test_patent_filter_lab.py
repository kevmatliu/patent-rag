from __future__ import annotations

import json
from pathlib import Path

from image_extract import CompoundOccurrence, CompoundPatent, ExtractionTuning
from scripts.patent_filter_lab import (
    build_google_patents_url,
    ensure_output_dir,
    save_compounds,
    write_manifest,
    write_summary,
)


def test_build_google_patents_url():
    assert build_google_patents_url("US20250042916A1") == "https://patents.google.com/patent/US20250042916A1/en"


def test_ensure_output_dir_clears_previous_contents(tmp_path: Path):
    output_dir = tmp_path / "test-uploads" / "US20250042916A1"
    nested = output_dir / "raw"
    nested.mkdir(parents=True)
    (nested / "old.png").write_bytes(b"old")

    ensure_output_dir(output_dir, keep_existing=False)

    assert output_dir.exists()
    assert list(output_dir.iterdir()) == []


def test_save_compounds_and_manifest(tmp_path: Path):
    output_dir = tmp_path / "test-uploads" / "US20250042916A1"
    raw_dir = output_dir / "raw"
    filtered_dir = output_dir / "filtered"
    patent = CompoundPatent(
        patent_id="US20250042916A1",
        compounds=[
            CompoundOccurrence(
                compound_number="1",
                page=3,
                image_bytes=b"png-bytes",
                bbox=(1, 2, 3, 4),
                metadata={"complexity_score": 123.4},
            )
        ],
    )

    raw_records = save_compounds(patent, raw_dir, prefix="raw")
    filtered_records = save_compounds(patent, filtered_dir, prefix="filtered")
    write_manifest(
        output_dir,
        patent.patent_id,
        ExtractionTuning(),
        raw_records,
        filtered_records,
        pdf_name="US20250042916A1.pdf",
    )
    write_summary(
        output_dir,
        patent.patent_id,
        pdf_size=42,
        raw_count=len(raw_records),
        filtered_count=len(filtered_records),
        tuning=ExtractionTuning(),
    )

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["patent_id"] == "US20250042916A1"
    assert manifest["raw_count"] == 1
    assert manifest["filtered_count"] == 1
    assert manifest["raw_records"][0]["page"] == 3
    assert (output_dir / manifest["raw_records"][0]["image_path"]).exists()
    assert (output_dir / "summary.txt").exists()
