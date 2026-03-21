from __future__ import annotations

import importlib.util
import inspect
import shutil
import sys
import types
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from PIL import Image

from app.core.config import Settings


class ExtractionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.module_path = Path(__file__).resolve().parents[2] / "image_extract.py"
        self._module: Optional[types.ModuleType] = None

    def module_exists(self) -> bool:
        return self.module_path.exists()

    def load_module(self) -> types.ModuleType:
        if self._module is not None:
            return self._module
        if not self.module_exists():
            raise FileNotFoundError(
                f"Expected extractor module at {self.module_path}."
            )

        spec = importlib.util.spec_from_file_location("external_image_extract", self.module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not load extractor module from {self.module_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        self._module = module
        return module

    def _candidate_functions(self, module: types.ModuleType) -> list[Callable[..., Any]]:
        candidates: list[Callable[..., Any]] = []
        for name in (
            "extract_from_patent",
            "extract_from_scanned_pdf",
            "extract_images_from_patent",
            "extract_images",
        ):
            candidate = getattr(module, name, None)
            if callable(candidate):
                candidates.append(candidate)
        return candidates

    def _invoke_extractor(self, extractor: Callable[..., Any], url: str, patent_slug: str, pdf_bytes: bytes) -> Any:
        parameters = list(inspect.signature(extractor).parameters.values())
        required = [
            parameter
            for parameter in parameters
            if parameter.default is inspect._empty
            and parameter.kind in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
        ]
        required_count = len(required)

        if extractor.__name__ == "extract_from_scanned_pdf":
            if required_count <= 1:
                return extractor(pdf_bytes)
            return extractor(pdf_bytes, patent_slug)

        if required_count == 1:
            return extractor(url)
        if required_count == 2:
            return extractor(url, patent_slug)
        if required_count >= 3:
            return extractor(url, patent_slug, pdf_bytes)
        return extractor()

    def _iter_image_payloads(self, raw_result: Any) -> Iterable[Any]:
        if raw_result is None:
            return []
        if hasattr(raw_result, "get_compounds") and callable(raw_result.get_compounds):
            return raw_result.get_compounds()
        if isinstance(raw_result, (list, tuple)):
            return raw_result
        if hasattr(raw_result, "compounds"):
            return getattr(raw_result, "compounds")
        raise TypeError(
            "Unsupported extractor return type. Expected a list/tuple, an object with get_compounds(), or an object with compounds."
        )

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

    def extract_from_patent(self, url: str, patent_slug: str, pdf_bytes: bytes) -> list[dict[str, object]]:
        module = self.load_module()
        candidates = self._candidate_functions(module)
        if not candidates:
            raise RuntimeError(
                "image_extract.py does not expose a supported callable. Add one of: extract_from_patent, extract_from_scanned_pdf, extract_images_from_patent, extract_images."
            )

        last_error: Optional[Exception] = None
        for extractor in candidates:
            try:
                raw_result = self._invoke_extractor(extractor, url=url, patent_slug=patent_slug, pdf_bytes=pdf_bytes)
                saved_records: list[dict[str, object]] = []
                output_dir = self.settings.extracted_image_dir / patent_slug
                for index, payload in enumerate(self._iter_image_payloads(raw_result), start=1):
                    saved_records.append(
                        {
                            "image_path": self._save_payload(payload, output_dir, index),
                            "page_number": self._extract_page_number(payload),
                        }
                    )
                return saved_records
            except Exception as exc:
                last_error = exc
                continue

        if last_error is None:
            raise RuntimeError("Extractor failed without exposing a concrete error")
        raise RuntimeError(f"Extractor invocation failed: {last_error}") from last_error
