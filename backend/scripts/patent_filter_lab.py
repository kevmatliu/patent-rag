from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

from app.core.config import get_settings
from app.services.patent_fetch_service import PatentFetchService
from image_extract import (
    CompoundOccurrence,
    CompoundPatent,
    ExtractionTuning,
    extract_candidate_compounds,
    filter_patent,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch a patent PDF locally and dump raw/filtered extraction crops for heuristic tuning.",
    )
    parser.add_argument("patent_id", help="Patent code like US20250042916A1")
    parser.add_argument(
        "--output-root",
        default=str(Path(__file__).resolve().parents[1] / "test-uploads"),
        help="Directory where patent dumps will be written",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Keep an existing output directory instead of clearing old files",
    )
    parser.add_argument("--render-scale", type=float, default=3.0)
    parser.add_argument("--binary-threshold", type=int, default=220)
    parser.add_argument("--dilation-kernel-size", type=int, default=2)
    parser.add_argument("--min-width", type=int, default=120)
    parser.add_argument("--min-height", type=int, default=120)
    parser.add_argument("--max-page-fraction", type=float, default=0.8)
    parser.add_argument("--padding", type=int, default=10)
    parser.add_argument("--density-min", type=float, default=0.003)
    parser.add_argument("--density-max", type=float, default=0.25)
    parser.add_argument("--complexity-bins", type=int, default=80)
    parser.add_argument("--complexity-smooth-sigma", type=float, default=2.0)
    parser.add_argument(
        "--skip-filter",
        action="store_true",
        help="Only dump raw candidates and skip the bimodal complexity filter",
    )
    return parser.parse_args()


def build_tuning(args: argparse.Namespace) -> ExtractionTuning:
    return ExtractionTuning(
        render_scale=args.render_scale,
        binary_threshold=args.binary_threshold,
        dilation_kernel_size=args.dilation_kernel_size,
        min_width=args.min_width,
        min_height=args.min_height,
        max_page_fraction=args.max_page_fraction,
        padding=args.padding,
        density_min=args.density_min,
        density_max=args.density_max,
        complexity_bins=args.complexity_bins,
        complexity_smooth_sigma=args.complexity_smooth_sigma,
    )


def ensure_output_dir(output_dir: Path, keep_existing: bool) -> None:
    if output_dir.exists() and not keep_existing:
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def build_google_patents_url(patent_id: str) -> str:
    return f"https://patents.google.com/patent/{patent_id}/en"


def save_compounds(patent: CompoundPatent, directory: Path, prefix: str) -> list[dict[str, object]]:
    directory.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    for index, compound in enumerate(patent.get_compounds(), start=1):
        filename = f"{prefix}_{index:04d}_page_{compound.page}.png"
        image_path = directory / filename
        image_path.write_bytes(compound.image_bytes)
        records.append(compound_to_record(compound, image_path.relative_to(directory.parent)))
    return records


def compound_to_record(compound: CompoundOccurrence, relative_path: Path) -> dict[str, object]:
    return {
        "compound_number": compound.compound_number,
        "page": compound.page,
        "bbox": list(compound.bbox),
        "image_path": relative_path.as_posix(),
        "metadata": compound.metadata,
    }


def write_manifest(
    output_dir: Path,
    patent_id: str,
    tuning: ExtractionTuning,
    raw_records: list[dict[str, object]],
    filtered_records: list[dict[str, object]],
    pdf_name: str,
) -> None:
    manifest = {
        "patent_id": patent_id,
        "pdf_path": pdf_name,
        "tuning": asdict(tuning),
        "raw_count": len(raw_records),
        "filtered_count": len(filtered_records),
        "raw_records": raw_records,
        "filtered_records": filtered_records,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def write_summary(
    output_dir: Path,
    patent_id: str,
    pdf_size: int,
    raw_count: int,
    filtered_count: int,
    tuning: ExtractionTuning,
) -> None:
    summary = "\n".join(
        [
            f"patent_id={patent_id}",
            f"pdf_bytes={pdf_size}",
            f"raw_candidates={raw_count}",
            f"filtered_candidates={filtered_count}",
            f"render_scale={tuning.render_scale}",
            f"binary_threshold={tuning.binary_threshold}",
            f"dilation_kernel_size={tuning.dilation_kernel_size}",
            f"min_width={tuning.min_width}",
            f"min_height={tuning.min_height}",
            f"max_page_fraction={tuning.max_page_fraction}",
            f"padding={tuning.padding}",
            f"density_min={tuning.density_min}",
            f"density_max={tuning.density_max}",
            f"complexity_bins={tuning.complexity_bins}",
            f"complexity_smooth_sigma={tuning.complexity_smooth_sigma}",
        ]
    )
    (output_dir / "summary.txt").write_text(summary + "\n", encoding="utf-8")


def main() -> int:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    args = parse_args()
    settings = get_settings()
    fetch_service = PatentFetchService(settings)

    patent_id = args.patent_id.strip()
    tuning = build_tuning(args)
    output_root = Path(args.output_root).resolve()
    output_dir = output_root / patent_id
    ensure_output_dir(output_dir, keep_existing=args.keep_existing)

    print(f"Fetching patent {patent_id}...")
    fetch_result = fetch_service.fetch(build_google_patents_url(patent_id))
    pdf_path = output_dir / f"{patent_id}.pdf"
    pdf_path.write_bytes(fetch_result.pdf_bytes)
    print(f"Saved PDF to {pdf_path}")

    raw_patent = extract_candidate_compounds(fetch_result.pdf_bytes, patent_id, tuning=tuning)
    raw_dir = output_dir / "raw"
    raw_records = save_compounds(raw_patent, raw_dir, prefix="raw")
    print(f"Saved {len(raw_records)} raw candidate images to {raw_dir}")

    filtered_records: list[dict[str, object]] = []
    if args.skip_filter:
        print("Skipping complexity filter as requested.")
    else:
        filtered_patent = CompoundPatent(
            patent_id=raw_patent.patent_id,
            compounds=[
                CompoundOccurrence(
                    compound_number=compound.compound_number,
                    page=compound.page,
                    image_bytes=compound.image_bytes,
                    bbox=compound.bbox,
                    assay_data=dict(compound.assay_data),
                    smiles_data=compound.smiles_data,
                    metadata=dict(compound.metadata),
                )
                for compound in raw_patent.get_compounds()
            ],
        )
        filtered_patent = filter_patent(filtered_patent, tuning=tuning)
        filtered_dir = output_dir / "filtered"
        filtered_records = save_compounds(filtered_patent, filtered_dir, prefix="filtered")
        print(f"Saved {len(filtered_records)} filtered images to {filtered_dir}")

    write_manifest(
        output_dir,
        patent_id,
        tuning,
        raw_records,
        filtered_records,
        pdf_name=pdf_path.name,
    )
    write_summary(
        output_dir,
        patent_id,
        pdf_size=len(fetch_result.pdf_bytes),
        raw_count=len(raw_records),
        filtered_count=len(filtered_records),
        tuning=tuning,
    )
    print(f"Wrote manifest to {output_dir / 'manifest.json'}")
    print(f"Wrote summary to {output_dir / 'summary.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
