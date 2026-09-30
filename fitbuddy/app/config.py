from functools import lru_cache
from typing import Any

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "FitBuddy"
    environment: str = "development"
    database_url: str = "sqlite:///./fitbuddy.db"
    gemini_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    )
    # Keep model names configurable because Google periodically retires models.
    gemini_workout_model: str = "gemini-3.6-flash"
    gemini_tip_model: str = "gemini-3.6-flash"
    gemini_timeout_seconds: float = 45.0
    admin_token: str | None = None
    log_level: str = "INFO"

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key and self.gemini_api_key.strip())

    def public_dict(self) -> dict[str, Any]:
        """Return non-secret settings useful for diagnostics."""
        return {
            "app_name": self.app_name,
            "environment": self.environment,
            "database_url": self.database_url,
            "gemini_configured": self.gemini_configured,
            "gemini_workout_model": self.gemini_workout_model,
            "gemini_tip_model": self.gemini_tip_model,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()

