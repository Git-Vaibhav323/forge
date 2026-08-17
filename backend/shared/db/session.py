from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

_engine = None
_SessionLocal = None


def configure_engine(database_url: str) -> None:
    global _engine, _SessionLocal
    kwargs: dict = {"pool_pre_ping": True}
    if database_url.startswith("postgresql"):
        kwargs.update(
            {
                "pool_size": 5,
                "max_overflow": 5,
                "pool_recycle": 280,
                "pool_timeout": 10,
                "connect_args": {
                    "connect_timeout": 8,
                    "keepalives": 1,
                    "keepalives_idle": 30,
                    "keepalives_interval": 10,
                    "keepalives_count": 3,
                },
            }
        )
    _engine = create_engine(database_url, **kwargs)
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
