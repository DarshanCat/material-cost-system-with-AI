"""
Transaction guard for operations that write to the append-only stock ledger.

* Any failure rolls the whole unit of work back (document status change, audit log and ledger rows
  together), so a rejected or failed approval never leaves a half-applied state in the session.
* A database integrity violation raised while posting (for example a concurrent approval of the same
  document tripping UNIQUE(source_document_type, source_line_id), or a ledger entry-number collision)
  is reported as HTTP 409 instead of an unhandled 500. Nothing is posted twice.

Note: row-level locking (SELECT ... FOR UPDATE) used by the callers is only effective on PostgreSQL;
SQLite ignores it. Concurrency behaviour therefore still needs verification on PostgreSQL.
"""

from contextlib import contextmanager

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@contextmanager
def ledger_write_guard(db: Session):
    try:
        yield
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflicting concurrent posting detected. Nothing was posted; please refresh and retry.",
        )
    except Exception:
        db.rollback()
        raise
