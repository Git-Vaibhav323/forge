import os

APP_ENV = os.environ.get("APP_ENV", "development")
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")

# TODO(Phase 2, see context.md → Build order): read DATABASE_URL, REDIS_URL,
# OBJECT_STORAGE_ENDPOINT, LLM_API_KEY here once those services are wired up.
