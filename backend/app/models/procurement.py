import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class CycleStatus(StrEnum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"
    COMPLETED = "completed"


class ProcurementCycle(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "procurement_cycles"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("categories.id"), nullable=True)
    order_window_opens_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    order_window_closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[CycleStatus] = mapped_column(
        Enum(CycleStatus, native_enum=False, length=20), default=CycleStatus.DRAFT, nullable=False
    )

    items: Mapped[list["ProcurementItem"]] = relationship(back_populates="cycle", cascade="all, delete-orphan")
    category: Mapped["Category | None"] = relationship()


class ProcurementItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Cached aggregation snapshot for a product within a cycle (recomputed on demand/close)."""

    __tablename__ = "procurement_items"
    __table_args__ = (UniqueConstraint("cycle_id", "product_id", name="uq_procurement_item_cycle_product"),)

    cycle_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("procurement_cycles.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("products.id"), nullable=False)
    total_quantity: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)

    cycle: Mapped[ProcurementCycle] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()
