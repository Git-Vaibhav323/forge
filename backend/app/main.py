"""
Legacy monolith entry point — use the gateway instead:

    uvicorn gateway.main:app --reload --port 8000

See backend/README.md for running project-service and file-service.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS
from app.routers import attributes, outputs, questions, reviews

app = FastAPI(
    title="ForgeData API (legacy)",
    version="0.1.0",
    description="Deprecated — use gateway.main:app on port 8000.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(attributes.router)
app.include_router(questions.router)
app.include_router(reviews.router)
app.include_router(outputs.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "mode": "legacy-stubs-only"}
