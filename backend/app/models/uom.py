from sqlalchemy import String, Boolean, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin


class UOM(Base, TimestampMixin):
    __tablename__ = "uoms"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    decimal_precision: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    items = relationship("MaterialItem", back_populates="base_uom")
    requests = relationship("ItemRequest", back_populates="proposed_uom")
