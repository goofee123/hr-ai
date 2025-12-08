"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "HRM-Core"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"

    # API
    api_v1_prefix: str = "/api/v1"

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # Database (Supabase PostgreSQL)
    database_url: str

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24  # 24 hours

    # Supabase JWT secret (from Dashboard > Settings > API > JWT Secret)
    supabase_jwt_secret: Optional[str] = None

    # Redis (for ARQ background jobs)
    redis_url: str = "redis://localhost:6379"

    # File Storage
    max_file_size_mb: int = 10
    allowed_resume_types: str = "application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    # External Integrations
    affinda_api_key: Optional[str] = None
    sendgrid_api_key: Optional[str] = None

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:8000"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def allowed_resume_types_list(self) -> list[str]:
        """Parse allowed resume types from comma-separated string."""
        return [t.strip() for t in self.allowed_resume_types.split(",")]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
