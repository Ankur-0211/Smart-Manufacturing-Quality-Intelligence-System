"""Application configuration settings (roadmap Section 9.6)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SMQI_", env_file=".env", extra="ignore")

    ENV: str = "dev"
    INTELLIGENCE_BACKEND: str = "real"
    STAGE_PRESENTATION_MS: int = 1200
    STAGE_CACHE_SIZE: int = 5000
    DATABASE_URL: str = "sqlite:///./var/smqi.db"
    CORS_ORIGINS: list[str] = ["*"]
    API_KEY: str | None = None
    DATA_DIR: str = "data"
    MODEL_DIR: str = "models"


settings = Settings()
