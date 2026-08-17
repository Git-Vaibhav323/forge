from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.question_service.config import settings
from services.question_service.routers import questions
from shared.db.session import configure_engine

configure_engine(settings.database_url)

app = FastAPI(title="ForgeData Question Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(questions.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    from shared.llm_ranker import LlmSettings
    from services.question_service.config import settings as s

    llm = LlmSettings(provider=s.llm_provider, api_key=s.llm_api_key, model=s.llm_model)
    return {
        "status": "ok",
        "service": "question-service",
        "llm": s.llm_provider if llm.enabled else "off",
        "questionEngine": "hybrid",
    }
