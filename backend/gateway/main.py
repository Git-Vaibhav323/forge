"""
ForgeData API Gateway — public entry on :8000.

Proxies project routes → project-service (:8001)
Proxies file upload routes → file-service (:8002)
Other routes remain stub routers until their services merge.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import attributes, outputs, questions, reviews
from gateway.config import settings
from gateway.proxy import router as proxy_router

app = FastAPI(
    title="ForgeData API",
    version="0.2.0",
    description="Gateway for ForgeData microservices.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(proxy_router)
app.include_router(attributes.router)
app.include_router(questions.router)
app.include_router(reviews.router)
app.include_router(outputs.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "mode": "gateway"}
