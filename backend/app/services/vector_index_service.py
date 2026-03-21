from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Optional, Union

import faiss
import numpy as np


class VectorIndexService:
    def __init__(self, index_path: Path, mapping_path: Path) -> None:
        self.index_path = Path(index_path)
        self.mapping_path = Path(mapping_path)
        self.lock = threading.Lock()
        self.index: Optional[faiss.IndexFlatL2] = None
        self.id_map: list[int] = []

    @property
    def dimension(self) -> Optional[int]:
        if self.index is None:
            return None
        return int(self.index.d)

    def _ensure_index(self, dimension: int) -> None:
        if self.index is None:
            self.index = faiss.IndexFlatL2(dimension)
        elif self.index.d != dimension:
            raise ValueError(
                f"Vector dimension mismatch. Existing index uses {self.index.d}, incoming vector uses {dimension}."
            )

    def _normalize(self, vector: list[float]) -> np.ndarray:
        array = np.array(vector, dtype=np.float32)
        if array.ndim != 1:
            raise ValueError("Vector must be one-dimensional")
        return array

    def add_vector(self, image_id: int, vector: list[float]) -> None:
        array = self._normalize(vector)
        with self.lock:
            self._ensure_index(len(vector))
            assert self.index is not None
            self.index.add(array.reshape(1, -1))
            self.id_map.append(image_id)
            self.save()

    def search(self, vector: list[float], k: int) -> list[dict[str, Union[float, int]]]:
        array = self._normalize(vector)
        with self.lock:
            if self.index is None or self.index.ntotal == 0:
                return []
            limit = min(k, self.index.ntotal)
            distances, indices = self.index.search(array.reshape(1, -1), limit)

        results: list[dict[str, Union[float, int]]] = []
        for distance, internal_index in zip(distances[0], indices[0]):
            if internal_index == -1:
                continue
            results.append(
                {
                    "image_id": self.id_map[int(internal_index)],
                    "distance": float(distance),
                }
            )
        return results

    def save(self) -> None:
        if self.index is None:
            return
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.index_path))
        self.mapping_path.write_text(json.dumps(self.id_map), encoding="utf-8")

    def load(self) -> bool:
        if not self.index_path.exists() or not self.mapping_path.exists():
            return False
        with self.lock:
            self.index = faiss.read_index(str(self.index_path))
            self.id_map = json.loads(self.mapping_path.read_text(encoding="utf-8"))
            if self.index.ntotal != len(self.id_map):
                raise ValueError(
                    f"FAISS mapping mismatch. Index has {self.index.ntotal} vectors but mapping has {len(self.id_map)} items."
                )
        return True

    def rebuild(self, items: list[tuple[int, list[float]]]) -> None:
        with self.lock:
            if not items:
                self.index = None
                self.id_map = []
                if self.index_path.exists():
                    self.index_path.unlink()
                if self.mapping_path.exists():
                    self.mapping_path.unlink()
                return

            dimension = len(items[0][1])
            self.index = faiss.IndexFlatL2(dimension)
            self.id_map = []
            vectors: list[np.ndarray] = []

            for image_id, vector in items:
                normalized = self._normalize(vector)
                if len(normalized) != dimension:
                    raise ValueError("Cannot rebuild FAISS index with mixed embedding dimensions")
                self.id_map.append(image_id)
                vectors.append(normalized)

            self.index.add(np.stack(vectors))
            self.save()
