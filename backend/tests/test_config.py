from app.core.config import settings
from app.core.security import UserRole, ROLE_PERMISSIONS, Permission


def test_configuration_defaults():
    """Verify system defaults adhere to project specifications."""
    assert settings.PROJECT_NAME == "VSPL Material Management & Costing System"
    assert settings.COSTING_START_DATE == "2026-10-12"
    assert "localhost" in settings.sync_database_url
    assert "postgresql+psycopg://" in settings.sync_database_url


def test_cors_origins_validation():
    """Verify CORS origins parsing."""
    assert isinstance(settings.ALLOWED_ORIGINS, list)
    assert len(settings.ALLOWED_ORIGINS) >= 1


def test_rbac_matrix_definitions():
    """Verify all required industrial roles exist and permissions are structured."""
    expected_roles = {
        UserRole.STORES,
        UserRole.FOUNDRY,
        UserRole.PURCHASE,
        UserRole.MANAGEMENT,
        UserRole.ADMIN,
    }
    assert set(UserRole) == expected_roles

    # Verify each role has associated permissions defined
    for role in expected_roles:
        assert role in ROLE_PERMISSIONS
        assert len(ROLE_PERMISSIONS[role]) > 0

    # Verify critical business separation of duties:
    # Heat Log charge creation must belong to Foundry, but not direct Stock Adjustment
    assert Permission.HEAT_LOG_CREATE in ROLE_PERMISSIONS[UserRole.FOUNDRY]
    assert Permission.STOCK_ADJUST not in ROLE_PERMISSIONS[UserRole.FOUNDRY]
    assert Permission.STOCK_ADJUST in ROLE_PERMISSIONS[UserRole.STORES]
