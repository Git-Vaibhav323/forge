"""
ForgeData backend — API entry point (placeholder).

This wires the placeholder routers into one FastAPI app with CORS open to
the frontend. Only the Projects router has a working (in-memory) store; the
rest return empty lists or 501 until implemented. See context.md for the
full architecture and the phased build order.

Run:
    cd backend
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    uvicorn app.main:app --reload --port 8000

Then in the frontend set NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS
from app.routers import attributes, files, outputs, projects, questions, reviews

app = FastAPI(
    title="ForgeData API",
    version="0.1.0",
    description="Evidence-grounded industrial product intelligence (placeholder API).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(files.router)
app.include_router(attributes.router)
app.include_router(questions.router)
app.include_router(reviews.router)
app.include_router(outputs.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "mode": "placeholder"}
