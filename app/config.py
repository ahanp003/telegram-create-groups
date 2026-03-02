"""Application configuration via pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    api_id: int
    api_hash: str
    api_key: str
    test_mode: bool = False
    sessions_dir: str = "sessions_data"
    host: str = "0.0.0.0"
    port: int = 3579
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def get_settings() -> Settings:
    """Dependency for FastAPI to get settings."""
    return Settings()
