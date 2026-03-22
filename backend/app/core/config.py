from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(default="sqlite:///./app.db", alias="DATABASE_URL")
    faiss_index_path: Path = Field(
        default=Path("./faiss_index/index.bin"),
        alias="FAISS_INDEX_PATH",
    )
    faiss_mapping_path: Path = Field(
        default=Path("./faiss_index/mapping.json"),
        alias="FAISS_MAPPING_PATH",
    )
    model_device: str = Field(default="cpu", alias="MODEL_DEVICE")
    molscribe_model_path: Path = Field(
        default=Path("./models/molscribe/swin_base_char_aux_1m680k.pth"),
        alias="MOLSCRIBE_MODEL_PATH",
    )
    chemberta_model_path: Path = Field(
        default=Path("./models/chemberta"),
        alias="CHEMBERTA_MODEL_PATH",
    )
    upload_dir: Path = Field(default=Path("./uploads"), alias="UPLOAD_DIR")
    extracted_image_dir: Path = Field(
        default=Path("./uploads/extracted"),
        alias="EXTRACTED_IMAGE_DIR",
    )
    search_tmp_dir: Path = Field(
        default=Path("./uploads/search_tmp"),
        alias="SEARCH_TMP_DIR",
    )
    api_title: str = "Chemical Patent Search API"
    api_version: str = "2.0.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
        protected_namespaces=("settings_",),
    )

    def ensure_directories(self) -> None:
        for path in (
            self.faiss_index_path.parent,
            self.faiss_mapping_path.parent,
            self.upload_dir,
            self.extracted_image_dir,
            self.search_tmp_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
