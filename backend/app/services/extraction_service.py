from __future__ import annotations

import io
import math
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from PIL import Image

from app.core.config import Settings


@dataclass
class ExtractionTuning:
    raster_dpi: int = 300
    render_scale: float = 300.0 / 72.0
    binary_threshold: int = 220
    dilation_kernel_size: int = 4
    dilation_kernel_size_large: int = 20
    dilation_large_iterations: int = 2
    min_width: int = 120
    min_height: int = 120
    max_page_fraction: float = 0.85
    padding: int = 20
    density_min: float = 0.02
    density_max: float = 0.15
    complexity_bins: int = 80
    complexity_smooth_sigma: float = 2.0
    aspect_ratio_max: float = 6.0
    min_line_length: int = 15
    max_line_gap: int = 4
    hough_threshold: int = 20
    angle_tolerance_degrees: float = 8.0
    angle_alignment_min: float = 0.55
    angle_alignment_ring_override: float = 0.45
    border_endpoint_zone_ratio: float = 0.15
    border_endpoint_ratio_bonus_min: float = 0.15
    letter_width_min: int = 6
    letter_width_max: int = 22
    letter_aspect_ratio_min: float = 1.3
    letter_aspect_ratio_max: float = 4.0
    letter_component_ratio_max: float = 0.60
    nms_iou_threshold: float = 0.30
    nested_overlap_threshold: float = 0.60
    expansion_ratio: float = 0.08
    expansion_min_pixels: int = 20


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


@dataclass
class CandidateBox:
    bbox: tuple[int, int, int, int]
    density: float
    angle_alignment_score: float
    ring_count: int
    border_endpoint_ratio: float
    convex_hull_fill_ratio: float
    letter_component_ratio: float
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class ExtractionService:
    ANGLE_BUCKETS = (0.0, 30.0, 60.0, 90.0, 120.0, 150.0)

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @staticmethod
    def _require_extractor_dependencies():
        try:
            import cv2
            import fitz
            import numpy as np
        except ImportError as exc:
            raise RuntimeError(f"Missing extractor dependency: {exc}") from exc
        return cv2, fitz, np

    def module_exists(self) -> bool:
        return True

    def load_module(self) -> "ExtractionService":
        self._require_extractor_dependencies()
        return self

    @staticmethod
    def _raster_scale(tuning: ExtractionTuning) -> float:
        return tuning.raster_dpi / 72.0

    @staticmethod
    def _rect_area(bbox: tuple[int, int, int, int]) -> int:
        return max(0, bbox[2]) * max(0, bbox[3])

    @classmethod
    def _rect_intersection(
        cls,
        left: tuple[int, int, int, int],
        right: tuple[int, int, int, int],
    ) -> int:
        left_x1, left_y1, left_w, left_h = left
        right_x1, right_y1, right_w, right_h = right
        left_x2 = left_x1 + left_w
        left_y2 = left_y1 + left_h
        right_x2 = right_x1 + right_w
        right_y2 = right_y1 + right_h
        inter_w = max(0, min(left_x2, right_x2) - max(left_x1, right_x1))
        inter_h = max(0, min(left_y2, right_y2) - max(left_y1, right_y1))
        return inter_w * inter_h

    @classmethod
    def _rect_iou(
        cls,
        left: tuple[int, int, int, int],
        right: tuple[int, int, int, int],
    ) -> float:
        intersection = cls._rect_intersection(left, right)
        if intersection <= 0:
            return 0.0
        left_area = cls._rect_area(left)
        right_area = cls._rect_area(right)
        union = left_area + right_area - intersection
        if union <= 0:
            return 0.0
        return intersection / union

    @classmethod
    def _nested_overlap(
        cls,
        left: tuple[int, int, int, int],
        right: tuple[int, int, int, int],
    ) -> float:
        intersection = cls._rect_intersection(left, right)
        if intersection <= 0:
            return 0.0
        smaller = min(cls._rect_area(left), cls._rect_area(right))
        if smaller <= 0:
            return 0.0
        return intersection / smaller

    @staticmethod
    def _union_bbox(
        left: tuple[int, int, int, int],
        right: tuple[int, int, int, int],
    ) -> tuple[int, int, int, int]:
        left_x, left_y, left_w, left_h = left
        right_x, right_y, right_w, right_h = right
        x1 = min(left_x, right_x)
        y1 = min(left_y, right_y)
        x2 = max(left_x + left_w, right_x + right_w)
        y2 = max(left_y + left_h, right_y + right_h)
        return x1, y1, x2 - x1, y2 - y1

    @staticmethod
    def _expand_bbox(
        bbox: tuple[int, int, int, int],
        *,
        page_width: int,
        page_height: int,
        tuning: ExtractionTuning,
    ) -> tuple[int, int, int, int]:
        x, y, width, height = bbox
        expansion = max(int(round(tuning.expansion_ratio * max(width, height))), tuning.expansion_min_pixels)
        x1 = max(0, x - expansion)
        y1 = max(0, y - expansion)
        x2 = min(page_width, x + width + expansion)
        y2 = min(page_height, y + height + expansion)
        return x1, y1, x2 - x1, y2 - y1

    @staticmethod
    def _is_letter_component(width: int, height: int, tuning: ExtractionTuning) -> bool:
        if width <= 0 or height <= 0:
            return False
        if not (tuning.letter_width_min < width < tuning.letter_width_max):
            return False
        aspect_ratio = height / width
        return tuning.letter_aspect_ratio_min < aspect_ratio < tuning.letter_aspect_ratio_max

    @classmethod
    def _text_density_ratio(cls, thresh_crop: Any, tuning: ExtractionTuning) -> float:
        cv2, _, _ = cls._require_extractor_dependencies()
        component_count, _, stats, _ = cv2.connectedComponentsWithStats(thresh_crop, connectivity=8)
        letter_like = 0
        total_components = 0

        for index in range(1, component_count):
            width = int(stats[index, cv2.CC_STAT_WIDTH])
            height = int(stats[index, cv2.CC_STAT_HEIGHT])
            area = int(stats[index, cv2.CC_STAT_AREA])
            if area <= 2:
                continue
            total_components += 1
            if cls._is_letter_component(width, height, tuning):
                letter_like += 1

        if total_components == 0:
            return 0.0
        return letter_like / total_components

    @classmethod
    def _stroke_angle_alignment(
        cls,
        thresh_crop: Any,
        tuning: ExtractionTuning,
    ) -> tuple[float, list[tuple[int, int, int, int]]]:
        cv2, _, np = cls._require_extractor_dependencies()
        raw_lines = cv2.HoughLinesP(
            thresh_crop,
            1,
            np.pi / 180,
            threshold=tuning.hough_threshold,
            minLineLength=tuning.min_line_length,
            maxLineGap=tuning.max_line_gap,
        )
        if raw_lines is None:
            return 0.0, []

        aligned_length = 0.0
        total_length = 0.0
        lines: list[tuple[int, int, int, int]] = []
        for line in raw_lines:
            x1, y1, x2, y2 = line[0]
            lines.append((int(x1), int(y1), int(x2), int(y2)))
            dx = float(x2 - x1)
            dy = float(y2 - y1)
            length = math.hypot(dx, dy)
            if length <= 0:
                continue
            angle = math.degrees(math.atan2(dy, dx)) % 180.0
            total_length += length
            if any(abs(angle - bucket) <= tuning.angle_tolerance_degrees for bucket in cls.ANGLE_BUCKETS):
                aligned_length += length

        if total_length <= 0:
            return 0.0, lines
        return aligned_length / total_length, lines

    @classmethod
    def _border_endpoint_ratio(
        cls,
        lines: list[tuple[int, int, int, int]],
        width: int,
        height: int,
        tuning: ExtractionTuning,
    ) -> float:
        endpoints: list[tuple[int, int]] = []
        for x1, y1, x2, y2 in lines:
            endpoints.append((x1, y1))
            endpoints.append((x2, y2))

        if not endpoints or width <= 0 or height <= 0:
            return 0.0

        near_border = 0
        for ex, ey in endpoints:
            if (
                ex < width * tuning.border_endpoint_zone_ratio
                or ex > width * (1.0 - tuning.border_endpoint_zone_ratio)
                or ey < height * tuning.border_endpoint_zone_ratio
                or ey > height * (1.0 - tuning.border_endpoint_zone_ratio)
            ):
                near_border += 1
        return near_border / len(endpoints)

    @classmethod
    def _ring_signature(cls, gray_crop: Any, thresh_crop: Any) -> int:
        cv2, _, _ = cls._require_extractor_dependencies()
        ring_count = 0

        blurred = cv2.GaussianBlur(gray_crop, (5, 5), 0)
        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=max(12, min(gray_crop.shape[:2]) // 6),
            param1=60,
            param2=12,
            minRadius=6,
            maxRadius=max(8, min(gray_crop.shape[:2]) // 3),
        )
        if circles is not None:
            ring_count += int(len(circles[0]))

        contours, _ = cv2.findContours(thresh_crop, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            perimeter = cv2.arcLength(contour, True)
            area = cv2.contourArea(contour)
            if perimeter <= 0 or area <= 20:
                continue
            circularity = (4.0 * math.pi * area) / (perimeter * perimeter)
            if circularity >= 0.72:
                ring_count += 1

        return ring_count

    @classmethod
    def _candidate_from_bbox(
        cls,
        *,
        bbox: tuple[int, int, int, int],
        merged_contour: Any,
        thresh_for_crop: Any,
        gray: Any,
        page_width: int,
        page_height: int,
        tuning: ExtractionTuning,
    ) -> Optional[CandidateBox]:
        cv2, _, _ = cls._require_extractor_dependencies()
        x, y, width, height = bbox
        if width < tuning.min_width or height < tuning.min_height:
            return None
        if width >= page_width * tuning.max_page_fraction or height >= page_height * tuning.max_page_fraction:
            return None

        longest_side = max(width, height)
        shortest_side = min(width, height)
        if shortest_side <= 0:
            return None
        if longest_side > 1500:
            return None

        aspect_ratio = longest_side / shortest_side
        if aspect_ratio > tuning.aspect_ratio_max:
            return None

        thresh_crop = thresh_for_crop[y : y + height, x : x + width]
        gray_crop = gray[y : y + height, x : x + width]
        density = float(thresh_crop.astype(bool).sum()) / max(1, width * height)
        if density < tuning.density_min or density > tuning.density_max:
            return None

        angle_alignment, lines = cls._stroke_angle_alignment(thresh_crop, tuning)
        ring_count = cls._ring_signature(gray_crop, thresh_crop)
        border_endpoint_ratio = cls._border_endpoint_ratio(lines, width, height, tuning)
        letter_ratio = cls._text_density_ratio(thresh_crop, tuning)
        if letter_ratio > tuning.letter_component_ratio_max:
            return None

        hull = cv2.convexHull(merged_contour)
        hull_area = float(cv2.contourArea(hull))
        convex_hull_fill_ratio = hull_area / max(1, width * height)

        score = angle_alignment + min(0.10, ring_count * 0.03)
        if border_endpoint_ratio >= tuning.border_endpoint_ratio_bonus_min:
            score += 0.08
        if 0.30 <= convex_hull_fill_ratio <= 0.60:
            score += 0.05

        if angle_alignment < tuning.angle_alignment_min:
            if ring_count <= 0 or angle_alignment < tuning.angle_alignment_ring_override:
                return None

        return CandidateBox(
            bbox=bbox,
            density=density,
            angle_alignment_score=angle_alignment,
            ring_count=ring_count,
            border_endpoint_ratio=border_endpoint_ratio,
            convex_hull_fill_ratio=convex_hull_fill_ratio,
            letter_component_ratio=letter_ratio,
            score=score,
            metadata={
                "raw_bbox": bbox,
                "density": density,
                "aspect_ratio": aspect_ratio,
                "angle_alignment_score": angle_alignment,
                "ring_count": ring_count,
                "border_endpoint_ratio": border_endpoint_ratio,
                "convex_hull_fill_ratio": convex_hull_fill_ratio,
                "letter_component_ratio": letter_ratio,
                "score": score,
                "tuning": asdict(tuning),
            },
        )

    @classmethod
    def is_chemical_structure(cls, thresh_crop: Any, tuning: Optional[ExtractionTuning] = None) -> bool:
        tuning = tuning or ExtractionTuning()
        height, width = thresh_crop.shape[:2]
        if width < tuning.min_width or height < tuning.min_height:
            return False

        shortest_side = min(width, height)
        longest_side = max(width, height)
        if shortest_side <= 0:
            return False
        if longest_side / shortest_side > tuning.aspect_ratio_max:
            return False

        density = float(thresh_crop.astype(bool).sum()) / max(1, width * height)
        return tuning.density_min <= density <= tuning.density_max

    @classmethod
    def _non_max_suppression(
        cls,
        candidates: list[CandidateBox],
        tuning: ExtractionTuning,
    ) -> list[CandidateBox]:
        kept: list[CandidateBox] = []
        for candidate in sorted(candidates, key=lambda item: item.score, reverse=True):
            merged = candidate
            next_kept: list[CandidateBox] = []
            for existing in kept:
                iou = cls._rect_iou(merged.bbox, existing.bbox)
                nested_overlap = cls._nested_overlap(merged.bbox, existing.bbox)
                if iou >= tuning.nms_iou_threshold or nested_overlap >= tuning.nested_overlap_threshold:
                    merged = CandidateBox(
                        bbox=cls._union_bbox(merged.bbox, existing.bbox),
                        density=max(merged.density, existing.density),
                        angle_alignment_score=max(merged.angle_alignment_score, existing.angle_alignment_score),
                        ring_count=max(merged.ring_count, existing.ring_count),
                        border_endpoint_ratio=max(
                            merged.border_endpoint_ratio,
                            existing.border_endpoint_ratio,
                        ),
                        convex_hull_fill_ratio=max(
                            merged.convex_hull_fill_ratio,
                            existing.convex_hull_fill_ratio,
                        ),
                        letter_component_ratio=min(
                            merged.letter_component_ratio,
                            existing.letter_component_ratio,
                        ),
                        score=max(merged.score, existing.score),
                        metadata={**existing.metadata, **merged.metadata},
                    )
                else:
                    next_kept.append(existing)
            next_kept.append(merged)
            kept = sorted(next_kept, key=lambda item: item.score, reverse=True)
        return kept

    @staticmethod
    def _smooth_counts(counts: Any, sigma: float = 2.0) -> Any:
        _, _, np = ExtractionService._require_extractor_dependencies()
        radius = max(1, int(4 * sigma))
        x = np.arange(-radius, radius + 1)
        kernel = np.exp(-(x**2) / (2 * sigma**2))
        kernel = kernel / kernel.sum()
        return np.convolve(counts, kernel, mode="same")

    @staticmethod
    def _find_local_peaks(arr: Any) -> list[int]:
        peaks: list[int] = []
        for index in range(1, len(arr) - 1):
            if arr[index] > arr[index - 1] and arr[index] > arr[index + 1]:
                peaks.append(index)
        return peaks

    @classmethod
    def find_valley_threshold(
        cls,
        scores: Any,
        bins: int = 80,
        smooth_sigma: float = 2.0,
    ) -> float:
        _, _, np = cls._require_extractor_dependencies()
        scores_array = np.asarray(scores)
        if scores_array.size == 0:
            raise ValueError("Empty scores array")

        counts, bin_edges = np.histogram(scores_array, bins=bins)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
        smoothed = cls._smooth_counts(counts, sigma=smooth_sigma)
        peaks = cls._find_local_peaks(smoothed)

        if len(peaks) < 2:
            return float(np.quantile(scores_array, 0.25))

        peak_vals = [(idx, smoothed[idx]) for idx in peaks]
        peak_vals.sort(key=lambda item: item[1], reverse=True)
        peak_one, peak_two = peak_vals[0][0], peak_vals[1][0]
        left, right = (peak_one, peak_two) if peak_one < peak_two else (peak_two, peak_one)
        valley_idx = left + int(np.argmin(smoothed[left : right + 1]))
        return float(bin_centers[valley_idx])

    @classmethod
    def filter_bimodal_keep_larger(
        cls,
        scores: Any,
        bins: int = 80,
        smooth_sigma: float = 2.0,
    ) -> tuple[Optional[float], Any, Any]:
        _, _, np = cls._require_extractor_dependencies()
        scores_array = np.asarray(scores)
        if scores_array.size == 0:
            return None, np.zeros(0, dtype=bool), np.array([])

        threshold = cls.find_valley_threshold(scores_array, bins=bins, smooth_sigma=smooth_sigma)
        mask = scores_array >= threshold
        kept = scores_array[mask]
        return float(threshold), mask, kept

    @classmethod
    def score_structure_complexity(cls, image_bytes: bytes) -> float:
        cv2, _, np = cls._require_extractor_dependencies()
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

    @classmethod
    def filter_patent(
        cls,
        patent: CompoundPatent,
        tuning: Optional[ExtractionTuning] = None,
    ) -> CompoundPatent:
        _, _, np = cls._require_extractor_dependencies()
        tuning = tuning or ExtractionTuning()
        scores = [cls.score_structure_complexity(compound.image_bytes) for compound in patent.get_compounds()]
        threshold, mask, kept_scores = cls.filter_bimodal_keep_larger(
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
        patent.compounds = np.array(patent.get_compounds(), dtype=object)[mask].tolist()

        for index, compound in enumerate(patent.get_compounds(), start=1):
            compound.compound_number = str(index)
            compound.metadata["complexity_threshold"] = threshold
            compound.metadata["kept_after_filter"] = True

        return patent

    @classmethod
    def extract_candidate_compounds(
        cls,
        pdf_bytes: bytes,
        patent_id: str,
        tuning: Optional[ExtractionTuning] = None,
    ) -> CompoundPatent:
        cv2, fitz, np = cls._require_extractor_dependencies()
        tuning = tuning or ExtractionTuning()
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
        patent = CompoundPatent(patent_id=patent_id)

        try:
            for page_number, page in enumerate(document, start=1):
                pix = page.get_pixmap(matrix=fitz.Matrix(cls._raster_scale(tuning), cls._raster_scale(tuning)))
                image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
                if pix.n == 4:
                    image_bgr = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
                elif pix.n == 1:
                    image_bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
                else:
                    image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

                gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
                _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

                kernel_size_small = max(3, min(5, tuning.dilation_kernel_size))
                kernel_small = np.ones((kernel_size_small, kernel_size_small), np.uint8)
                kernel_size_large = max(15, min(25, tuning.dilation_kernel_size_large))
                kernel_large = np.ones((kernel_size_large, kernel_size_large), np.uint8)
                dilated_small = cv2.dilate(thresh, kernel_small, iterations=1)
                dilated_large = cv2.dilate(thresh, kernel_large, iterations=tuning.dilation_large_iterations)
                contours, _ = cv2.findContours(dilated_large, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                candidates: list[CandidateBox] = []
                for contour in contours:
                    bbox = cv2.boundingRect(contour)
                    candidate = cls._candidate_from_bbox(
                        bbox=bbox,
                        merged_contour=contour,
                        thresh_for_crop=dilated_small,
                        gray=gray,
                        page_width=pix.width,
                        page_height=pix.height,
                        tuning=tuning,
                    )
                    if candidate is not None:
                        candidates.append(candidate)

                selected = cls._non_max_suppression(candidates, tuning)
                for candidate in selected:
                    expanded_bbox = cls._expand_bbox(
                        candidate.bbox,
                        page_width=pix.width,
                        page_height=pix.height,
                        tuning=tuning,
                    )
                    x, y, width, height = expanded_bbox
                    crop = image_bgr[y : y + height, x : x + width]
                    ok, buffer = cv2.imencode(".png", crop)
                    if not ok:
                        continue

                    patent.add_compound(
                        CompoundOccurrence(
                            compound_number=None,
                            page=page_number,
                            image_bytes=buffer.tobytes(),
                            bbox=expanded_bbox,
                            assay_data={},
                            smiles_data=None,
                            metadata={
                                **candidate.metadata,
                                "raw_bbox": candidate.bbox,
                                "expanded_bbox": expanded_bbox,
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

    @classmethod
    def extract_from_scanned_pdf(
        cls,
        pdf_bytes: bytes,
        patent_id: str,
        tuning: Optional[ExtractionTuning] = None,
        filter_results: bool = False,
    ) -> CompoundPatent:
        patent = cls.extract_candidate_compounds(pdf_bytes, patent_id, tuning=tuning)
        if not filter_results:
            return patent
        return cls.filter_patent(patent, tuning=tuning)

    def _extract_page_number(self, payload: Any) -> Optional[int]:
        page = getattr(payload, "page", None)
        if isinstance(page, int):
            return page
        if isinstance(payload, dict) and isinstance(payload.get("page_number"), int):
            return payload["page_number"]
        if isinstance(payload, dict) and isinstance(payload.get("page"), int):
            return payload["page"]
        return None

    def _save_payload(self, payload: Any, output_dir: Path, index: int) -> str:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"compound_{index:04d}.png"

        if isinstance(payload, str):
            source_path = Path(payload)
            if not source_path.exists():
                raise FileNotFoundError(f"Extractor returned missing file path: {payload}")
            shutil.copyfile(source_path, output_path)
            return str(output_path.resolve())

        if isinstance(payload, Path):
            if not payload.exists():
                raise FileNotFoundError(f"Extractor returned missing file path: {payload}")
            shutil.copyfile(payload, output_path)
            return str(output_path.resolve())

        if isinstance(payload, bytes):
            output_path.write_bytes(payload)
            return str(output_path.resolve())

        if isinstance(payload, Image.Image):
            payload.save(output_path, format="PNG")
            return str(output_path.resolve())

        image_bytes = getattr(payload, "image_bytes", None)
        if isinstance(image_bytes, bytes):
            output_path.write_bytes(image_bytes)
            return str(output_path.resolve())

        pil_image = getattr(payload, "image", None)
        if isinstance(pil_image, Image.Image):
            pil_image.save(output_path, format="PNG")
            return str(output_path.resolve())

        if hasattr(payload, "read") and callable(payload.read):
            data = payload.read()
            if not isinstance(data, bytes):
                raise TypeError("Extractor file-like payload did not return bytes")
            output_path.write_bytes(data)
            return str(output_path.resolve())

        if isinstance(payload, dict):
            if isinstance(payload.get("image_path"), str):
                source_path = Path(payload["image_path"])
                if not source_path.exists():
                    raise FileNotFoundError(f"Extractor returned missing image_path: {source_path}")
                shutil.copyfile(source_path, output_path)
                return str(output_path.resolve())
            if isinstance(payload.get("image_bytes"), bytes):
                output_path.write_bytes(payload["image_bytes"])
                return str(output_path.resolve())

        raise TypeError(
            "Unsupported extractor payload. Expected file path, bytes, PIL image, dict with image_path/image_bytes, or an object exposing image_bytes."
        )

    def extract_from_patent(
        self,
        url: str,
        patent_slug: str,
        pdf_bytes: bytes,
        tuning: Optional[ExtractionTuning] = None,
        filter_results: bool = False,
    ) -> list[dict[str, object]]:
        _ = url
        patent = self.extract_from_scanned_pdf(
            pdf_bytes,
            patent_slug,
            tuning=tuning,
            filter_results=filter_results,
        )
        output_dir = self.settings.extracted_image_dir / patent_slug
        saved_records: list[dict[str, object]] = []
        for index, payload in enumerate(patent.get_compounds(), start=1):
            saved_records.append(
                {
                    "image_path": self._save_payload(payload, output_dir, index),
                    "page_number": self._extract_page_number(payload),
                }
            )
        return saved_records
