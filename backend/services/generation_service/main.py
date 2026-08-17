from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.generation_service.config import settings
from services.generation_service.routers import outputs
from shared.db.session import configure_engine

configure_engine(settings.database_url)

app = FastAPI(title="ForgeData Generation Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(outputs.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "service": "generation-service"}
