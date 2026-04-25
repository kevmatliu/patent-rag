from __future__ import annotations

from app.services.extraction_service import (
    CompoundOccurrence,
    CompoundPatent,
    ExtractionService,
    ExtractionTuning,
)


is_chemical_structure = ExtractionService.is_chemical_structure
find_valley_threshold = ExtractionService.find_valley_threshold
filter_bimodal_keep_larger = ExtractionService.filter_bimodal_keep_larger
score_structure_complexity = ExtractionService.score_structure_complexity
filter_patent = ExtractionService.filter_patent
extract_candidate_compounds = ExtractionService.extract_candidate_compounds
extract_from_scanned_pdf = ExtractionService.extract_from_scanned_pdf


def extract_from_patent(
    url: str,
    patent_slug: str,
    pdf_bytes: bytes,
    tuning: ExtractionTuning | None = None,
    filter_results: bool = True,
) -> CompoundPatent:
    _ = url
    return extract_from_scanned_pdf(
        pdf_bytes,
        patent_slug,
        tuning=tuning,
        filter_results=filter_results,
    )
