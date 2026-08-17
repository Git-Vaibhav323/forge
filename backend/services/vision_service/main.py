from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.vision_service.config import settings
from services.vision_service.routers import vision
from shared.db.session import configure_engine

configure_engine(settings.database_url)

app = FastAPI(title="ForgeData Vision Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vision.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "service": "vision-service"}
