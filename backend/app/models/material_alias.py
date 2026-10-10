"""
Material Description Alias Master Models.
Enables mapping from raw heat-log descriptions (e.g. 'CRC Scrap-Low High MN')
to controlled material items without altering historical source data.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List

from sqlalchemy import (
    String,
    DateTime,
    Boolean,
    Integer,
    ForeignKey,
    Text,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AliasApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class MaterialAlias(Base):
    """
    Material Alias record.
    Maps a raw descriptive string from heat logs to an official MaterialItem.
    """
    __tablename__ = "material_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alias_text: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_alias_key: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    
    material_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("material_items.id"), nullable=False, index=True
    )
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), default=AliasApprovalStatus.APPROVED.value, nullable=False, index=True
    )
    
    reviewer_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
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

    material_item = relationship("MaterialItem")
    audit_logs: Mapped[List["MaterialAliasAuditLog"]] = relationship(
        "MaterialAliasAuditLog",
        back_populates="alias",
        cascade="all, delete-orphan",
        order_by="MaterialAliasAuditLog.timestamp",
    )


class MaterialAliasAuditLog(Base):
    """
    Audit log for material alias lifecycle and reviews.
    """
    __tablename__ = "material_alias_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alias_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("material_aliases.id", ondelete="CASCADE"), nullable=False, index=True
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

    alias = relationship("MaterialAlias", back_populates="audit_logs")
