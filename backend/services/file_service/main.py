from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.file_service.config import settings
from services.file_service.routers import files
from services.file_service.storage import ensure_bucket
from shared.db.session import configure_engine

configure_engine(settings.database_url)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_bucket()
    yield


app = FastAPI(title="ForgeData File Service", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(files.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "service": "file-service"}
