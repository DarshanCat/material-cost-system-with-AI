from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import String, Text, ForeignKey, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin


class RequestStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class ItemRequest(Base, TimestampMixin):
    __tablename__ = "item_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    requested_name: Mapped[str] = mapped_column(String(255), nullable=False)
    proposed_department_id: Mapped[int] = mapped_column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    proposed_category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    proposed_subcategory: Mapped[str | None] = mapped_column(String(50), nullable=True)
    proposed_uom_id: Mapped[int] = mapped_column(Integer, ForeignKey("uoms.id"), nullable=False, index=True)
    justification: Mapped[str] = mapped_column(Text, nullable=False)

    requester_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    requester_role: Mapped[str] = mapped_column(String(50), nullable=False)
    requester_department: Mapped[str] = mapped_column(String(100), nullable=False)

    status: Mapped[str] = mapped_column(String(20), default=RequestStatus.DRAFT.value, nullable=False, index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    reviewer_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    decision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_comments: Mapped[str | None] = mapped_column(Text, nullable=True)

    linked_item_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("material_items.id"), nullable=True)

    # Relationships
    proposed_department = relationship("Department", back_populates="requests")
    proposed_uom = relationship("UOM", back_populates="requests")
    linked_item = relationship("MaterialItem", back_populates="item_requests")
    audit_logs = relationship("ItemRequestAuditLog", back_populates="request", cascade="all, delete-orphan", order_by="ItemRequestAuditLog.timestamp")


class ItemRequestAuditLog(Base):
    __tablename__ = "item_request_audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(Integer, ForeignKey("item_requests.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(50), nullable=False)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    request = relationship("ItemRequest", back_populates="audit_logs")
