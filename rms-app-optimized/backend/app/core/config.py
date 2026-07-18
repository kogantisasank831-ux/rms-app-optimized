"""Application settings (pydantic-settings). Reads env, falls back to rms-app/.env for local dev."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# rms-app/.env  (config.py -> core -> app -> backend -> rms-app)
_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Database (shared PG hack_db_02; team schema) ---
    DATABASE_URL: str
    PG_SCHEMA: str = "public"

    # --- MinIO (single provided bucket; prefixes for cvs/offers/templates) ---
    MINIO_ENDPOINT: str = ""
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_SECURE: bool = False
    MINIO_BUCKET: str = ""

    # --- AI ---
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-opus-4-8"

    # --- Auth / app ---
    JWT_SECRET: str = "dev-only-change-me"
    JWT_EXPIRE_MINUTES: int = 480
    CORS_ORIGINS: str = "http://localhost:3000"
    APP_ENV: str = "dev"
    MAX_UPLOAD_MB: int = 10
    AGENT_TIMEOUT_S: int = 60
    AUTO_SCREEN_ON_CREATE: bool = True  # auto-run resume_screening when an application is created
    AUTO_SUMMARIZE_FEEDBACK: bool = True  # auto-run feedback_summarization after feedback is saved
    AUTO_GENERATE_QUESTIONS: bool = True  # pre-generate interview_questions in the background on scheduling

    @property
    def sync_database_url(self) -> str:
        """psycopg (sync) URL for Alembic; app runtime uses the async DATABASE_URL."""
        return self.DATABASE_URL.replace("+asyncpg", "+psycopg")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> "Settings":
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
