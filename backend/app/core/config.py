"""Application settings (roadmap Section 9.6).

All variables use the ``SMQI_`` prefix and are loaded from the environment and an
optional ``.env`` file. ``.env.example`` documents every variable.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Repository root: backend/app/core/config.py -> parents[3]
REPO_ROOT = Path(__file__).resolve().parents[3]


class Environment(StrEnum):
    DEV = "dev"
    TEST = "test"
    DEMO = "demo"


class IntelligenceBackendMode(StrEnum):
    """Which ``QualityIntelligence`` implementation is wired in (roadmap 9.1, UD-11)."""

    MOCK = "mock"
    HYBRID = "hybrid"
    REAL = "real"


class LogFormat(StrEnum):
    JSON = "json"
    CONSOLE = "console"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SMQI_",
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    # --- Role 2 ---
    env: Environment = Environment.DEV
    database_url: str = f"sqlite:///{(REPO_ROOT / 'var' / 'smqi.db').as_posix()}"
    # R2-P5 task 11: Role 1's facade is the default; tests and offline work opt into "mock".
    intelligence_backend: IntelligenceBackendMode = IntelligenceBackendMode.REAL
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )
    api_key: str | None = None
    log_level: str = "INFO"
    log_format: LogFormat = LogFormat.JSON
    stage_presentation_ms: int = Field(default=1500, ge=1200, le=2000)
    stage_cache_size: int = Field(default=5000, ge=0)
    rate_limit_per_min: int = Field(default=30, ge=1)

    # --- Role 1 (consumed read-only by the application) ---
    model_dir: Path = REPO_ROOT / "models"
    fusion_model_version: str = "active"
    anomaly_model_version: str = "active"
    stage_stats_version: str = "active"
    constraints_path: Path = REPO_ROOT / "backend" / "app" / "domain" / "constraints.yaml"
    fleet_path: Path = REPO_ROOT / "backend" / "app" / "domain" / "fleet.yaml"
    recommend_time_budget_s: float = Field(default=5.0, gt=0)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("api_key", mode="before")
    @classmethod
    def _empty_key_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("model_dir", "constraints_path", "fleet_path", mode="after")
    @classmethod
    def _resolve_relative_to_repo(cls, value: Path) -> Path:
        return value if value.is_absolute() else (REPO_ROOT / value).resolve()

    @model_validator(mode="after")
    def _demo_requires_real_intelligence(self) -> Settings:
        # Roadmap 9.1 / 9.2: mock or hybrid outputs must never appear in a demo.
        if (
            self.env is Environment.DEMO
            and self.intelligence_backend is not IntelligenceBackendMode.REAL
        ):
            raise ValueError(
                "SMQI_ENV=demo requires SMQI_INTELLIGENCE_BACKEND=real "
                f"(got '{self.intelligence_backend.value}')"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
