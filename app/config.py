"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    APP_NAME: str = "TransitIQ"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    GTFS_DATA_PATH: str = "data"
    FOUNDRY_PROJECT_ENDPOINT: str | None = None
    FOUNDRY_AZURE_OPENAI_ENDPOINT: str | None = None
    FOUNDRY_MODEL_DEPLOYMENT: str = "gpt-oss-120b"
    FOUNDRY_API_KEY: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()