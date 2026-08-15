"""Load backend/.env without treating % as interpolation (Windows / dotenv)."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_ROOT / ".env"

load_dotenv(ENV_FILE, interpolate=False, override=True)


def database_url_from_parts(
    *,
    user: str,
    password: str,
    host: str,
    port: str,
    name: str,
    sslmode: str = "require",
) -> str:
    encoded = quote_plus(password)
    return (
        f"postgresql+psycopg://{user}:{encoded}@{host}:{port}/{name}"
        f"?sslmode={sslmode}"
    )
