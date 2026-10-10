"""
Induction Furnace Issue-to-Heat Reconciliation Models.
Persists deterministic three-pass reconciliation runs, discrepancy classifications,
fuzzy match candidates, and exception resolution audit trails.
"""

from datetime import date, datetime, timezone
from enum import Enum
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    String,
    DateTime,
    Date,
    Numeric,
    Integer,
    ForeignKey,
    Text,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class VarianceClass(str, Enum):
    OK = "OK"
    SHORT_ISSUE = "SHORT_ISSUE"        # Charged > Issued beyond tolerance
    EXCESS_ISSUE = "EXCESS_ISSUE"      # Issued > Charged beyond tolerance
    DECIMAL_SUSPECT = "DECIMAL_SUSPECT"  # Suspected order of magnitude scale discrepancy
    UNMATCHED_SLIP = "UNMATCHED_SLIP"  # Issue slip without matching heat
    UNMATCHED_HEAT = "UNMATCHED_HEAT"  # Heat charge without matching issue slip
    AMBIGUOUS_MATCH = "AMBIGUOUS_MATCH"  # Multiple potential match allocations
    UNMAPPED_MATERIAL = "UNMAPPED_MATERIAL"  # Charge description lacks approved alias
    PENDING_REVIEW = "PENDING_REVIEW"


class MatchMethod(str, Enum):
    EXACT_HEAT_SLIP = "EXACT_HEAT_SLIP"
    SAME_DAY_BATCH = "SAME_DAY_BATCH"
    MANUAL_CONFIRMED = "MANUAL_CONFIRMED"
    UNMATCHED_SLIP = "UNMATCHED_SLIP"
    UNMATCHED_HEAT = "UNMATCHED_HEAT"
    AMBIGUOUS_MATCH = "AMBIGUOUS_MATCH"


class CandidateMatchStatus(str, Enum):
    SUGGESTED = "SUGGESTED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class ExceptionStatus(str, Enum):
    OPEN = "OPEN"
    IN_INVESTIGATION = "IN_INVESTIGATION"
    RESOLVED = "RESOLVED"
    ACCEPTED_LOSS = "ACCEPTED_LOSS"


class ReconciliationRun(Base):
    """
    Reconciliation Run Header.
    Versioned execution snapshot of the 3-pass reconciliation engine.
    Reruns never overwrite previous runs.
    """
    __tablename__ = "reconciliation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(50), nullable=False, default="v1.0-3pass-deterministic")
    
    date_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    date_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="COMPLETED", index=True)
    
    total_evaluated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    exact_matches_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    batch_matches_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fuzzy_candidates_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    discrepancies_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    results: Mapped[List["ReconciliationResult"]] = relationship(
        "ReconciliationResult",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    candidate_matches: Mapped[List["ReconciliationCandidateMatch"]] = relationship(
        "ReconciliationCandidateMatch",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    exceptions: Mapped[List["ReconciliationException"]] = relationship(
        "ReconciliationException",
        back_populates="run",
        cascade="all, delete-orphan",
    )


class ReconciliationResult(Base):
    """
    Detailed comparison result for a matched or evaluated item in a reconciliation run.
    Stores exact formula variables, applied tolerances, and contributing source identifiers.
    """
    __tablename__ = "reconciliation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    material_item_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("material_items.id"), nullable=True, index=True
    )
    heat_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("heat_headers.id"), nullable=True, index=True
    )
    
    match_method: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # Quantities in NUMERIC(15, 4)
    issued_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False, default=Decimal("0.0000"))
    charged_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False, default=Decimal("0.0000"))
    
    # Signed variance convention: Issued - Charged
    variance_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    variance_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    
    # Applied tolerance parameters
    applied_tolerance: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    tolerance_basis: Mapped[str] = mapped_column(String(100), nullable=False)
    
    variance_class: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # JSON strings of contributing document IDs for full traceability
    contributing_issue_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contributing_issue_line_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contributing_heat_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contributing_charge_line_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="RESOLVED", nullable=False, index=True)

    run = relationship("ReconciliationRun", back_populates="results")
    material_item = relationship("MaterialItem")
    heat = relationship("HeatHeader")


class ReconciliationCandidateMatch(Base):
    """
    Pass 3 Advisory Fuzzy Match Candidate.
    Requires explicit human confirmation/rejection. Never auto-confirmed.
    """
    __tablename__ = "reconciliation_candidate_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    issue_line_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("material_issue_line_items.id"), nullable=False, index=True
    )
    heat_charge_line_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("heat_charge_lines.id"), nullable=False, index=True
    )
    
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)  # 0 to 100%
    suggestion_reason: Mapped[str] = mapped_column(Text, nullable=False)
    
    status: Mapped[str] = mapped_column(
        String(20), default=CandidateMatchStatus.SUGGESTED.value, nullable=False, index=True
    )
    
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    run = relationship("ReconciliationRun", back_populates="candidate_matches")
    issue_line = relationship("MaterialIssueLineItem")
    charge_line = relationship("HeatChargeLine")


class ReconciliationException(Base):
    """
    Exception item requiring investigation or operational action.
    """
    __tablename__ = "reconciliation_exceptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    exception_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    assigned_role: Mapped[str] = mapped_column(String(50), nullable=False, default="Foundry", index=True)
    priority: Mapped[str] = mapped_column(String(20), default="MEDIUM", nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=ExceptionStatus.OPEN.value, nullable=False, index=True
    )
    
    resolution_comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    run = relationship("ReconciliationRun", back_populates="exceptions")
    audit_logs: Mapped[List["ReconciliationExceptionAuditLog"]] = relationship(
        "ReconciliationExceptionAuditLog",
        back_populates="exception",
        cascade="all, delete-orphan",
        order_by="ReconciliationExceptionAuditLog.timestamp",
    )


class ReconciliationExceptionAuditLog(Base):
    """
    Audit log for reconciliation exception state transitions and assignments.
    """
    __tablename__ = "reconciliation_exception_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exception_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reconciliation_exceptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    to_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    exception = relationship("ReconciliationException", back_populates="audit_logs")
