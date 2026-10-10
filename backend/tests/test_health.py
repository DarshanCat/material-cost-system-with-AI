from unittest.mock import patch
from fastapi.testclient import TestClient


def test_health_endpoint_response_structure(client: TestClient):
    """Verify the health endpoint returns the standardized schema."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()

    assert data["app_name"] == "VSPL Material Management & Costing System"
    assert data["costing_start_date"] == "2026-10-12"
    assert "status" in data
    assert data["status"] in ("healthy", "degraded")
    assert "database" in data
    assert isinstance(data["database"]["connected"], bool)
    assert data["database"]["status"] in ("connected", "disconnected")


def test_health_with_mocked_connected_db(client: TestClient):
    """Verify health endpoint output when database connection succeeds."""
    with patch("app.api.v1.endpoints.health.check_database_connection", return_value=(True, "Operational")):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"]["connected"] is True
        assert data["database"]["status"] == "connected"


def test_health_with_mocked_disconnected_db(client: TestClient):
    """Verify health endpoint reports degraded status when database is disconnected."""
    with patch("app.api.v1.endpoints.health.check_database_connection", return_value=(False, "Connection refused")):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"]["connected"] is False
        assert data["database"]["status"] == "disconnected"


def test_db_check_fails_clearly_when_database_unreachable(client: TestClient):
    """Verify /db-check raises 503 with explicit error when database connection fails."""
    with patch("app.api.v1.endpoints.health.check_database_connection", return_value=(False, "Connection refused to PostgreSQL on localhost:5432")):
        response = client.get("/api/v1/health/db-check")
        assert response.status_code == 503
        error_detail = response.json()["detail"]
        assert error_detail["error"] == "Database connectivity failed"
        assert "Connection refused" in error_detail["message"]


def test_db_check_succeeds_when_database_reachable(client: TestClient):
    """Verify /db-check returns 200 when database connection is operational."""
    with patch("app.api.v1.endpoints.health.check_database_connection", return_value=(True, "Operational")):
        response = client.get("/api/v1/health/db-check")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connected"
