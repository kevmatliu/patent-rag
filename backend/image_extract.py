from __future__ import annotations

import io
from dataclasses import asdict, dataclass, field
from typing import Any, List, Optional, Union

import cv2
import fitz
import numpy as np
from PIL import Image


@dataclass
class ExtractionTuning:
    render_scale: float = 3.0
    binary_threshold: int = 220
    dilation_kernel_size: int = 2
    min_width: int = 120
    min_height: int = 120
    max_page_fraction: float = 0.8
    padding: int = 10
    density_min: float = 0.01
    density_max: float = 0.12
    complexity_bins: int = 80
    complexity_smooth_sigma: float = 2.0


@dataclass
class CompoundOccurrence:
    compound_number: Optional[str]
    page: int
    image_bytes: bytes
    bbox: tuple[int, int, int, int]
    assay_data: dict[str, Any] = field(default_factory=dict)
    smiles_data: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompoundPatent:
    patent_id: str
    compounds: list[CompoundOccurrence] = field(default_factory=list)

    def add_compound(self, compound: CompoundOccurrence) -> None:
        self.compounds.append(compound)

    def get_compounds(self) -> list[CompoundOccurrence]:
        return self.compounds


def is_chemical_structure(thresh_crop: np.ndarray, tuning: Optional[ExtractionTuning] = None) -> bool:
    tuning = tuning or ExtractionTuning()
    height, width = thresh_crop.shape[:2]
    total_pixels = height * width
    black_pixels = cv2.countNonZero(thresh_crop)

    if total_pixels == 0:
        return False

    density = black_pixels / total_pixels
    if density > tuning.density_max or density < tuning.density_min:
        return False

    return True


def _smooth_counts(counts: np.ndarray, sigma: float = 2.0) -> np.ndarray:
    radius = max(1, int(4 * sigma))
    x = np.arange(-radius, radius + 1)
    kernel = np.exp(-(x**2) / (2 * sigma**2))
    kernel = kernel / kernel.sum()
    return np.convolve(counts, kernel, mode="same")


def _find_local_peaks(arr: np.ndarray) -> list[int]:
    peaks: list[int] = []
    for i in range(1, len(arr) - 1):
        if arr[i] > arr[i - 1] and arr[i] > arr[i + 1]:
            peaks.append(i)
    return peaks


def find_valley_threshold(
    scores: Union[np.ndarray, List[float]],
    bins: int = 80,
    smooth_sigma: float = 2.0,
) -> float:
    scores_array = np.asarray(scores)
    if scores_array.size == 0:
        raise ValueError("Empty scores array")

    counts, bin_edges = np.histogram(scores_array, bins=bins)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
    smoothed = _smooth_counts(counts, sigma=smooth_sigma)
    peaks = _find_local_peaks(smoothed)

    if len(peaks) < 2:
        return float(np.quantile(scores_array, 0.25))

    peak_vals = [(idx, smoothed[idx]) for idx in peaks]
    peak_vals.sort(key=lambda x: x[1], reverse=True)
    peak_one, peak_two = peak_vals[0][0], peak_vals[1][0]
    left, right = (peak_one, peak_two) if peak_one < peak_two else (peak_two, peak_one)
    valley_idx = left + int(np.argmin(smoothed[left : right + 1]))
    return float(bin_centers[valley_idx])


def filter_bimodal_keep_larger(
    scores: Union[np.ndarray, List[float]],
    bins: int = 80,
    smooth_sigma: float = 2.0,
) -> tuple[Optional[float], np.ndarray, np.ndarray]:
    scores_array = np.asarray(scores)
    if scores_array.size == 0:
        return None, np.zeros(0, dtype=bool), np.array([])

    threshold = find_valley_threshold(scores_array, bins=bins, smooth_sigma=smooth_sigma)
    mask = scores_array >= threshold
    kept = scores_array[mask]
    return float(threshold), mask, kept


def score_structure_complexity(image_bytes: bytes) -> float:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    arr = np.array(image)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    ink_ratio = float((bw > 0).mean())
    edges = cv2.Canny(gray, 50, 150)
    edge_ratio = float((edges > 0).mean())

    height, width = gray.shape[:2]
    area = float(height * width)
    return (ink_ratio * 2.0 + edge_ratio * 3.0) * area


def filter_patent(patent: CompoundPatent, tuning: Optional[ExtractionTuning] = None) -> CompoundPatent:
    tuning = tuning or ExtractionTuning()
    scores = [score_structure_complexity(compound.image_bytes) for compound in patent.get_compounds()]
    threshold, mask, kept_scores = filter_bimodal_keep_larger(
        scores,
        bins=tuning.complexity_bins,
        smooth_sigma=tuning.complexity_smooth_sigma,
    )

    for compound, score in zip(patent.get_compounds(), scores):
        compound.metadata["complexity_score"] = score

    if threshold is None:
        return patent

    print(
        f"Filtering compounds for {patent.patent_id} with threshold {threshold:.4f}: "
        f"keeping {len(kept_scores)}/{len(scores)}"
    )
    filtered_compounds = np.array(patent.get_compounds(), dtype=object)[mask].tolist()
    patent.compounds = filtered_compounds

    for index, compound in enumerate(patent.get_compounds(), start=1):
        compound.compound_number = str(index)
        compound.metadata["complexity_threshold"] = threshold
        compound.metadata["kept_after_filter"] = True

    return patent


def extract_candidate_compounds(pdf_bytes: bytes, patent_id: str, tuning: Optional[ExtractionTuning] = None) -> CompoundPatent:
    tuning = tuning or ExtractionTuning()
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    patent = CompoundPatent(patent_id=patent_id)

    try:
        for page_number, page in enumerate(document, start=1):
            pix = page.get_pixmap(matrix=fitz.Matrix(tuning.render_scale, tuning.render_scale))
            image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
            if pix.n == 4:
                image_bgr = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
            elif pix.n == 1:
                image_bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            else:
                image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

            gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

            kernel = np.ones((tuning.dilation_kernel_size, tuning.dilation_kernel_size), np.uint8)
            dilated = cv2.dilate(thresh, kernel, iterations=1)
            contours, _ = cv2.findContours(dilated, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            
            for contour in contours:
                x, y, width, height = cv2.boundingRect(contour)
                if width <= tuning.min_width or height <= tuning.min_height:
                    continue
                if width >= pix.width * tuning.max_page_fraction or height >= pix.height * tuning.max_page_fraction:
                    continue

                thresh_crop = thresh[y : y + height, x : x + width]
                if not is_chemical_structure(thresh_crop, tuning=tuning):
                    continue

                pad = tuning.padding
                y1, y2 = max(0, y - pad), min(pix.h, y + height + pad)
                x1, x2 = max(0, x - pad), min(pix.w, x + width + pad)
                crop = image_bgr[y1:y2, x1:x2]
                ok, buffer = cv2.imencode(".png", crop)
                if not ok:
                    continue

                density = cv2.countNonZero(thresh_crop) / max(1, thresh_crop.shape[0] * thresh_crop.shape[1])
                patent.add_compound(
                    CompoundOccurrence(
                        compound_number=None,
                        page=page_number,
                        image_bytes=buffer.tobytes(),
                        bbox=(x1, y1, x2 - x1, y2 - y1),
                        assay_data={},
                        smiles_data=None,
                        metadata={
                            "raw_bbox": (x, y, width, height),
                            "density": density,
                            "tuning": asdict(tuning),
                        },
                    )
                )

            print(
                f"Finished page {page_number} for {patent_id}. "
                f"Found {len(patent.get_compounds())} raw compound candidates so far."
            )
    finally:
        document.close()

    return patent


def extract_from_scanned_pdf(
    pdf_bytes: bytes,
    patent_id: str,
    tuning: Optional[ExtractionTuning] = None,
    filter_results: bool = True,
) -> CompoundPatent:
    patent = extract_candidate_compounds(pdf_bytes, patent_id, tuning=tuning)
    if not filter_results:
        return patent
    return filter_patent(patent, tuning=tuning)


def extract_from_patent(
    url: str,
    patent_slug: str,
    pdf_bytes: bytes,
    tuning: Optional[ExtractionTuning] = None,
    filter_results: bool = True,
) -> CompoundPatent:
    _ = url
    return extract_from_scanned_pdf(pdf_bytes, patent_slug, tuning=tuning, filter_results=filter_results)
