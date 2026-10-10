import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Ensure backend root is on sys.path
backend_path = Path(__file__).resolve().parents[1]
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.main import app
from app.core.config import settings


@pytest.fixture
def client() -> TestClient:
    """Fixture providing a TestClient for FastAPI."""
    with TestClient(app) as test_client:
        yield test_client
