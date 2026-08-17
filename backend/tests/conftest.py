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
def project_client(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setattr("services.project_service.repository.remove_object", lambda *_args, **_kwargs: None)

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

    from services.file_service.main import app
    from services.file_service.routers import files as files_router

    configure_engine(TEST_DATABASE_URL)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[files_router.get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def evidence_client(db_session: Session) -> Generator[TestClient, None, None]:
    from services.evidence_service.main import app
    from services.evidence_service.routers import attributes as attributes_router

    configure_engine(TEST_DATABASE_URL)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[attributes_router.get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def review_client(db_session: Session) -> Generator[TestClient, None, None]:
    from services.review_service.main import app
    from services.review_service.routers import reviews as reviews_router

    configure_engine(TEST_DATABASE_URL)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[reviews_router.get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def relationship_client(db_session: Session) -> Generator[TestClient, None, None]:
    from services.relationship_service.main import app
    from services.relationship_service.routers import relationships as rel_router

    configure_engine(TEST_DATABASE_URL)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[rel_router.get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def vision_client(db_session: Session) -> Generator[TestClient, None, None]:
    from services.vision_service.main import app
    from services.vision_service.routers import vision as vision_router

    configure_engine(TEST_DATABASE_URL)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[vision_router.get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def generation_client(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> Generator[TestClient, None, None]:
    # Artifact bytes are kept in memory so the suite needs no object storage.
    store: dict[str, bytes] = {}
    monkeypatch.setattr(
        "services.generation_service.repository._put",
        lambda key, data, content_type: store.__setitem__(key, data),
    )
    monkeypatch.setattr(
        "services.generation_service.repository._get", lambda key: store[key]
    )
    monkeypatch.setattr(
        "services.generation_service.repository._remove",
        lambda key: store.pop(key, None),
    )

    from services.generation_service.main import app
    from services.generation_service.routers import outputs as outputs_router

    configure_engine(TEST_DATABASE_URL)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[outputs_router.get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def question_client(db_session: Session) -> Generator[TestClient, None, None]:
    from services.question_service.main import app
    from services.question_service.routers import questions as questions_router

    configure_engine(TEST_DATABASE_URL)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[questions_router.get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
