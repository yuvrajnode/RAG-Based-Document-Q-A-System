"""Application settings.

Everything is read from the environment (or a local .env) so the same image can
run in dev and in a container without code changes. See .env.example.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

EmbeddingProvider = Literal["sentence-transformers", "voyage", "openai", "hashing"]
VectorStoreKind = Literal["chroma", "numpy"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="VERBATIM_",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM ---
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    llm_model: str = "claude-sonnet-5"
    llm_max_tokens: int = 1024
    llm_temperature: float = 0.0

    # --- Embeddings ---
    embedding_provider: EmbeddingProvider = "sentence-transformers"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_batch_size: int = 32
    embedding_dim: int = 384  # only consulted by the hashing provider
    voyage_api_key: str = Field(default="", validation_alias="VOYAGE_API_KEY")
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")

    # --- Storage ---
    vector_store: VectorStoreKind = "chroma"
    storage_dir: Path = Path("./storage")
    collection_name: str = "documents"

    # --- Chunking ---
    chunk_size: int = 900
    chunk_overlap: int = 150

    # --- Retrieval ---
    top_k: int = 5
    candidate_k: int = 40
    hybrid_alpha: float = 0.6  # 1.0 = dense only, 0.0 = lexical only
    use_mmr: bool = True
    mmr_lambda: float = 0.65
    min_score: float = 0.15

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:5173"
    max_upload_mb: int = 25

    @field_validator("hybrid_alpha", "mmr_lambda")
    @classmethod
    def _unit_interval(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("must be between 0 and 1")
        return v

    @field_validator("chunk_overlap")
    @classmethod
    def _sane_overlap(cls, v: int) -> int:
        if v < 0:
            raise ValueError("chunk_overlap cannot be negative")
        return v

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)

    def ensure_dirs(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        (self.storage_dir / "uploads").mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
