from __future__ import annotations

from pathlib import Path

from app.core.runtime_env import configure_model_runtime_env


class ChemBertaService:
    def __init__(self, model_path: Path, device: str = "cpu") -> None:
        self.model_path = Path(model_path)
        self.device = device
        self._tokenizer = None
        self._model = None

    def is_ready(self) -> tuple[bool, str]:
        if not self.model_path.exists():
            return False, f"ChemBERTa model path does not exist: {self.model_path}"
        try:
            self._load_model()
        except Exception as exc:
            return False, str(exc)
        return True, "ready"

    def _load_model(self) -> None:
        if self._tokenizer is not None and self._model is not None:
            return
        if not self.model_path.exists():
            raise FileNotFoundError(f"ChemBERTa model path does not exist: {self.model_path}")

        configure_model_runtime_env()

        import torch
        from transformers import AutoModel, AutoTokenizer

        self._tokenizer = AutoTokenizer.from_pretrained(
            str(self.model_path),
            local_files_only=True,
        )
        self._model = AutoModel.from_pretrained(
            str(self.model_path),
            local_files_only=True,
        )
        self._model.to(self.device)
        self._model.eval()

    def smiles_to_embedding(self, smiles: str) -> list[float]:
        if not smiles.strip():
            raise ValueError("Cannot generate an embedding from an empty SMILES string")

        configure_model_runtime_env()

        import torch

        self._load_model()
        assert self._tokenizer is not None
        assert self._model is not None

        tokens = self._tokenizer(
            smiles,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        )
        tokens = {key: value.to(self.device) for key, value in tokens.items()}

        with torch.no_grad():
            outputs = self._model(**tokens)
            embedding_tensor = outputs.last_hidden_state[:, 0, :].detach().cpu().flatten()

        return embedding_tensor.tolist()
