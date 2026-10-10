import sys
from pathlib import Path
from typing import Generator
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

# Ensure backend root is on sys.path
backend_path = Path(__file__).resolve().parents[1]
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

import app.models  # Register all models with Base.metadata before importing app
from app.main import app as fastapi_app
from app.db.base import Base
from app.db.session import get_db
from app.db.seed import seed_reference_data


# Isolated in-memory engine explicitly for unit tests
TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """
    Provides an isolated clean database session for each test function.
    Creates schema, seeds reference master data (8 departments, standard UOMs),
    and drops all tables on teardown.
    """
    Base.metadata.create_all(bind=TEST_ENGINE)
    db = TestingSessionLocal()
    seed_reference_data(db)
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Fixture providing a TestClient with database session overridden."""
    def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def stores_headers() -> dict[str, str]:
    return {
        "X-User-Id": "usr_stores_01",
        "X-User-Role": "Stores",
        "X-User-Department": "General/Stores",
    }


@pytest.fixture
def foundry_headers() -> dict[str, str]:
    return {
        "X-User-Id": "usr_foundry_01",
        "X-User-Role": "Foundry",
        "X-User-Department": "Foundry",
    }


@pytest.fixture
def purchase_headers() -> dict[str, str]:
    return {
        "X-User-Id": "usr_purchase_01",
        "X-User-Role": "Purchase",
        "X-User-Department": "Purchase",
    }


@pytest.fixture
def management_headers() -> dict[str, str]:
    return {
        "X-User-Id": "usr_mgmt_01",
        "X-User-Role": "Management",
        "X-User-Department": "Management",
    }


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {
        "X-User-Id": "usr_admin_01",
        "X-User-Role": "Admin",
        "X-User-Department": "Admin",
    }
