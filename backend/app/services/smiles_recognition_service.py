from __future__ import annotations

from typing import Protocol


class SmilesRecognitionService(Protocol):
    name: str
    device: str

    def is_ready(self) -> tuple[bool, str]:
        ...

    def image_to_smiles(self, image_path: str) -> str:
        ...
