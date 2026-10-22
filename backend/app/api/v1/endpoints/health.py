from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.config import settings
from app.core.security import AuthenticatedUser, Permission, require_permission
from app.db.session import check_database_connection
from app.schemas.health import HealthResponse, DatabaseHealth

router = APIRouter()


@router.get("", response_model=HealthResponse, summary="System Health Status")
def get_health() -> HealthResponse:
    """
    Returns application and database connectivity status.
    Gracefully reports database status as 'disconnected' if PostgreSQL is not currently running,
    enabling frontend and local tools to query system status without server crashes.
    """
    db_ok, db_msg = check_database_connection()
    db_health = DatabaseHealth(
        connected=db_ok,
        status="connected" if db_ok else "disconnected",
        message=db_msg,
    )

    return HealthResponse(
        status="healthy" if db_ok else "degraded",
        app_name=settings.PROJECT_NAME,
        environment=settings.ENVIRONMENT,
        version="0.1.0",
        costing_start_date=settings.COSTING_START_DATE,
        database=db_health,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/db-check", summary="Strict Database Connectivity Verification")
def verify_db_connectivity(
    _user: AuthenticatedUser = Depends(require_permission(Permission.AUDIT_READ)),
):
    """
    Strict database verification endpoint.
    Fails with HTTP 503 Service Unavailable if database connection cannot be established,
    providing automated QA and CI/CD pipelines with a decisive connectivity gate.
    """
    db_ok, db_msg = check_database_connection()
    if not db_ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Database connectivity failed",
                "message": db_msg,
                "configured_target": f"{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}",
            },
        )
    return {
        "status": "connected",
        "message": "PostgreSQL database reachable and responding",
        "target": f"{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}",
    }
