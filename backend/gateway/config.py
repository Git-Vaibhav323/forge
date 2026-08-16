from pydantic_settings import BaseSettings, SettingsConfigDict

import shared.load_env  # noqa: F401


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    app_env: str = "development"
    cors_origins: str = (
        "http://localhost:3000,http://localhost:3001,http://localhost:3002,"
        "http://127.0.0.1:3000,http://127.0.0.1:3001,http://127.0.0.1:3002"
    )
    project_service_url: str = "http://localhost:8001"
    file_service_url: str = "http://localhost:8002"
    question_service_url: str = "http://localhost:8003"
    evidence_service_url: str = "http://localhost:8004"


settings = Settings()
