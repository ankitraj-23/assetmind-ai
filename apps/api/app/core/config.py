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

    # Persistence backend selector. Defaults to the existing local JSON/filesystem
    # pipeline; "postgres" is reserved for the upcoming database-backed path.
    # Nothing connects to a database while this is "json".
    persistence_backend: str = "json"

    # Optional Postgres connection string (e.g.
    # "postgresql+psycopg://assetmind:assetmind@localhost:5432/assetmind").
    # Left unset by default so the API boots with zero database configuration.
    # No connection is opened at import time.
    database_url: str | None = None

    # Browser origins allowed to call the API (the Next.js dev server by default).
    # Override with a comma-separated CORS_ORIGINS environment variable.
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()


def use_postgres() -> bool:
    """Return True when the Postgres persistence backend is selected.

    Case/whitespace-insensitive so ``PERSISTENCE_BACKEND=Postgres`` works. When
    this is False the API uses the default JSON/filesystem pipeline and never
    touches the database.
    """
    return settings.persistence_backend.strip().lower() == "postgres"
