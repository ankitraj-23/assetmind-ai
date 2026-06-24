"""Application configuration for the AssetMind AI API.

Settings are loaded via pydantic-settings and may be overridden through
environment variables. Sensible defaults keep the backend runnable without
any local configuration.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the API service."""

    project_name: str = "AssetMind AI API"
    service_name: str = "assetmind-ai-api"
    environment: str = "development"

    # Local directory where uploaded originals and document metadata are stored.
    storage_dir: str = "storage"

    # Browser origins allowed to call the API (the Next.js dev server by default).
    # Override with a comma-separated CORS_ORIGINS environment variable.
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
