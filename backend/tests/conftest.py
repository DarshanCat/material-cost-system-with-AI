import os
import sys
from pathlib import Path
from typing import Generator
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

# Security configuration must be fixed BEFORE the app/settings are imported: tests run with the
# development-only signed-token provider; identity is never taken from X-User-* headers.
os.environ["ENVIRONMENT"] = "test"
os.environ["AUTH_PROVIDER"] = "dev"
os.environ["SECRET_KEY"] = "test-only-secret-key-not-for-any-real-environment"

# Ensure backend root is on sys.path
backend_path = Path(__file__).resolve().parents[1]
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

import app.models  # Register all models with Base.metadata before importing app
from app.main import app as fastapi_app
from app.db.base import Base
from app.db.session import get_db
from app.db.seed import seed_reference_data
from app.core.auth import DEV_USERS, issue_dev_token
from app.core.security import UserRole


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


def _bearer(role: UserRole) -> dict[str, str]:
    """Authorization header carrying a signed token for the fixed server-side dev account of `role`."""
    return {"Authorization": f"Bearer {issue_dev_token(DEV_USERS[role])}"}


@pytest.fixture
def anon_client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient with no credentials (alias of `client`, named for security tests)."""
    def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def stores_headers() -> dict[str, str]:
    return _bearer(UserRole.STORES)


@pytest.fixture
def foundry_headers() -> dict[str, str]:
    return _bearer(UserRole.FOUNDRY)


@pytest.fixture
def purchase_headers() -> dict[str, str]:
    return _bearer(UserRole.PURCHASE)


@pytest.fixture
def management_headers() -> dict[str, str]:
    return _bearer(UserRole.MANAGEMENT)


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return _bearer(UserRole.ADMIN)


@pytest.fixture
def role_headers():
    """Callable returning bearer headers for any role (used by the route-by-role matrix)."""
    return _bearer


@pytest.fixture(scope="function")
def pg_session_factory():
    """
    Opt-in PostgreSQL session factory for live PostgreSQL schema, trigger, and
    multi-session concurrency verification.
    Activated only when TEST_POSTGRES_URL is set and points strictly to the
    isolated disposable test database (127.0.0.1:55432/vspl_mm_test).
    """
    pg_url = os.environ.get("TEST_POSTGRES_URL")
    if not pg_url:
        pytest.skip("TEST_POSTGRES_URL not set; skipping live PostgreSQL test.")

    parsed = make_url(pg_url)
    if parsed.host != "127.0.0.1" or parsed.port != 55432 or parsed.database != "vspl_mm_test":
        pytest.fail(
            f"Safety guard tripped: TEST_POSTGRES_URL must target 127.0.0.1:55432/vspl_mm_test, "
            f"got {parsed.host}:{parsed.port}/{parsed.database}"
        )

    pg_engine = create_engine(
        pg_url,
        pool_size=10,
        max_overflow=10,
        pool_pre_ping=True,
    )
    PgSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=pg_engine,
    )

    with PgSessionLocal() as setup_db:
        db_name = setup_db.execute(text("SELECT current_database()")).scalar_one()
        assert db_name == "vspl_mm_test", f"Expected vspl_mm_test, got {db_name}"
        seed_reference_data(setup_db)

    try:
        yield PgSessionLocal
    finally:
        pg_engine.dispose()
