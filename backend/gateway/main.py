"""
ForgeData API Gateway — public entry on :8000.

Proxies project routes → project-service (:8001)
Proxies file upload routes → file-service (:8002)
Proxies question routes → question-service (:8003)
Proxies attribute/evidence routes → evidence-service (:8004)
Proxies review/decision routes → review-service (:8005)
Proxies output/download routes → generation-service (:8008)

Every public route is now a proxy — there are no stub routers left.
relationship-service (:8006) and vision-service (:8007) stay internal.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
    # Next.dev hops to 3001/3002 when 3000 is busy; 127.0.0.1 is a different origin.
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(proxy_router)


@app.exception_handler(Exception)
async def gateway_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal gateway error"},
    )


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "mode": "gateway"}
