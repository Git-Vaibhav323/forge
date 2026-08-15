from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from shared.db.base import Base
from shared.db.session import configure_engine

TEST_DATABASE_URL = __import__("os").environ.get("TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")


@pytest.fixture(scope="session")
def engine():
    if TEST_DATABASE_URL.startswith("sqlite"):
        test_engine = create_engine(
            TEST_DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        test_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)

    Base.metadata.create_all(bind=test_engine)
    configure_engine(TEST_DATABASE_URL)
    yield test_engine
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session(engine) -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, autocommit=False, autoflush=False)()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def project_client(db_session: Session) -> Generator[TestClient, None, None]:
    from services.project_service.main import app
    from services.project_service.routers import projects as projects_router

    configure_engine(TEST_DATABASE_URL)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[projects_router.get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def file_client(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setattr("services.file_service.storage.put_object", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.file_service.storage.remove_object", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.file_service.storage.ensure_bucket", lambda: None)

    class MockHttpxClient:
        async def get(self, _url: str, **_kwargs):
            class Response:
                status_code = 200

            return Response()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    monkeypatch.setattr(
        "services.file_service.routers.files.httpx.AsyncClient",
        lambda **_kwargs: MockHttpxClient(),
    )

    from services.file_service.main import app
    from services.file_service.routers import files as files_router

    configure_engine(TEST_DATABASE_URL)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[files_router.get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
