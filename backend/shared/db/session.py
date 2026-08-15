from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

_engine = None
_SessionLocal = None


def configure_engine(database_url: str) -> None:
    global _engine, _SessionLocal
    _engine = create_engine(database_url, pool_pre_ping=True)
    _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


def get_session_factory() -> sessionmaker[Session]:
    if _SessionLocal is None:
        raise RuntimeError("Database not configured — call configure_engine first")
    return _SessionLocal


def get_db(database_url: str) -> Generator[Session, None, None]:
    configure_engine(database_url)
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
