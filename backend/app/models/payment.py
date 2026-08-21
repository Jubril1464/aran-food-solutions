import uuid
from enum import StrEnum

from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCESSFUL = "successful"
    FAILED = "failed"
    REFUNDED = "refunded"


class Payment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("provider", "reference", name="uq_payment_provider_reference"),)

    order_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("orders.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="paystack")
    reference: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, native_enum=False, length=20), default=PaymentStatus.PENDING, nullable=False
    )
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    order: Mapped["Order"] = relationship(back_populates="payments")
