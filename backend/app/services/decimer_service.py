from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional

from app.core.runtime_env import configure_model_runtime_env


class DecimerService:
    name = "decimer"

    def __init__(self, model_path: Path, device: str = "cpu") -> None:
        self.model_path = Path(model_path)
        self.device = device
        self._predict_smiles: Optional[Callable[[str], str]] = None

    def is_ready(self) -> tuple[bool, str]:
        if not self.model_path.exists():
            return False, f"DECIMER model path does not exist: {self.model_path}"
        try:
            self._load_predictor()
        except Exception as exc:
            return False, str(exc)
        return True, "ready"

    def _load_predictor(self) -> Callable[[str], str]:
        if self._predict_smiles is not None:
            return self._predict_smiles

        if not self.model_path.exists():
            raise FileNotFoundError(f"DECIMER model path does not exist: {self.model_path}")

        configure_model_runtime_env()
        os.environ.setdefault("PYSTOW_HOME", str(self.model_path.parent))
        try:
            from DECIMER import predict_SMILES
        except Exception as exc:
            raise RuntimeError(f"Failed to import DECIMER: {exc}") from exc

        self._predict_smiles = predict_SMILES
        return self._predict_smiles

    def image_to_smiles(self, image_path: str) -> str:
        predictor = self._load_predictor()
        temp_target: Optional[str] = None
        source_path = Path(image_path)

        try:
            if source_path.exists():
                temp_target = str(source_path)
            else:
                raise FileNotFoundError(f"Image path does not exist: {image_path}")
            smiles = predictor(temp_target)
            cleaned = (smiles or "").strip()
            if not cleaned:
                raise ValueError("DECIMER returned an empty SMILES string")
            return cleaned
        finally:
            if temp_target and temp_target != image_path:
                try:
                    Path(temp_target).unlink(missing_ok=True)
                except OSError:
                    pass
