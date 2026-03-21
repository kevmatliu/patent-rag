from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from app.core.runtime_env import configure_model_runtime_env


class MolScribeService:
    name = "molscribe"

    def __init__(self, model_path: Path, device: str = "cpu") -> None:
        self.model_path = Path(model_path)
        self.device = device
        self._predictor: Optional[Any] = None

    def is_ready(self) -> tuple[bool, str]:
        if not self.model_path.exists():
            return False, f"MolScribe model path does not exist: {self.model_path}"
        try:
            self._load_predictor()
        except Exception as exc:
            return False, str(exc)
        return True, "ready"

    def _load_predictor(self) -> Any:
        if self._predictor is not None:
            return self._predictor

        if not self.model_path.exists():
            raise FileNotFoundError(f"MolScribe model path does not exist: {self.model_path}")

        configure_model_runtime_env()

        try:
            from molscribe import MolScribe
        except Exception as exc:
            raise RuntimeError(f"Failed to import MolScribe: {exc}") from exc

        self._predictor = MolScribe(str(self.model_path), device=self.device)
        return self._predictor

    def image_to_smiles(self, image_path: str) -> str:
        predictor = self._load_predictor()
        source_path = Path(image_path)
        if not source_path.exists():
            raise FileNotFoundError(f"Image path does not exist: {image_path}")

        try:
            prediction = predictor.predict_image_file(str(source_path))
        except TypeError:
            prediction = predictor.predict_image_file(str(source_path), return_confidence=False)

        cleaned = self._normalize_prediction(prediction)
        if not cleaned:
            raise ValueError("MolScribe returned an empty SMILES string")
        return cleaned

    def _normalize_prediction(self, prediction: Any) -> str:
        if isinstance(prediction, str):
            return prediction.strip()
        if isinstance(prediction, tuple) and prediction:
            head = prediction[0]
            if isinstance(head, str):
                return head.strip()
        if isinstance(prediction, list) and prediction:
            head = prediction[0]
            if isinstance(head, str):
                return head.strip()
            if isinstance(head, dict):
                return str(
                    head.get("smiles")
                    or head.get("SMILES")
                    or head.get("prediction")
                    or ""
                ).strip()
        if isinstance(prediction, dict):
            return str(
                prediction.get("smiles")
                or prediction.get("SMILES")
                or prediction.get("prediction")
                or ""
            ).strip()
        return str(prediction or "").strip()
