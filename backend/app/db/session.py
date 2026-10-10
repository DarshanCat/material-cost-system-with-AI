"""
Database Session and Engine Management.
"""

from typing import Generator, Tuple
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings

# Engine configuration with pool_pre_ping to proactively verify connection health
engine = create_engine(
    settings.sync_database_url,
    pool_pre_ping=True,
    echo=False,
    connect_args={"connect_timeout": 3},
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Dependency that provides a transactional SQLAlchemy session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> Tuple[bool, str]:
    """
    Directly tests database connectivity.
    Returns:
        (True, "Database connection operational") if reachable,
        (False, error_message) if connection fails.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            return True, "Database connection operational"
    except SQLAlchemyError as exc:
        return False, f"Database connectivity failed: {str(exc.__class__.__name__)} - {str(exc)}"
    except Exception as exc:
        return False, f"Unexpected error while reaching database: {str(exc)}"
