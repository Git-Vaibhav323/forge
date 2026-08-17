from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

import shared.load_env  # noqa: F401
from shared.load_env import database_url_from_parts


class Settings(BaseSettings):
    # Env is loaded in shared.load_env with interpolate=False. Do not load
    # .env again here — python-dotenv would expand % in the password and
    # DATABASE_URL would fall back to localhost.
    model_config = SettingsConfigDict(extra="ignore")

    app_env: str = "development"
    cors_origins: str = "http://localhost:3000"
    database_url: str = "postgresql+psycopg://forgedata:forgedata@localhost:5433/forgedata"
    postgres_host: str | None = None
    postgres_port: str = "5432"
    postgres_db: str = "postgres"
    postgres_user: str = "postgres"
    postgres_password: str | None = None
    postgres_sslmode: str = "require"

    # Hybrid question engine — optional LLM ranking (free tier: Gemini or Groq).
    # LLM_PROVIDER=off disables LLM; rules + evidence still apply.
    llm_provider: str = "off"
    llm_api_key: str | None = None
    llm_model: str | None = None

    # Nameplate / image OCR (M7). Default OFF so the stack runs with no system
    # binaries installed — images are simply stored and read no facts, rather
    # than the scan failing. See shared/ocr.py.
    ocr_provider: str = "off"  # off | tesseract | custom
    ocr_api_url: str | None = None
    ocr_api_key: str | None = None
    tesseract_cmd: str | None = None

    @model_validator(mode="after")
    def apply_supabase_parts(self):
        if self.postgres_host and self.postgres_password:
            password = self.postgres_password.strip().strip('"').strip("'")
            self.database_url = database_url_from_parts(
                user=self.postgres_user,
                password=password,
                host=self.postgres_host,
                port=self.postgres_port,
                name=self.postgres_db,
                sslmode=self.postgres_sslmode,
            )
        return self


settings = Settings()

CORS_ORIGINS = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
DATABASE_URL = settings.database_url
