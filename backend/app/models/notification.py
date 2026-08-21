import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class NotificationType(StrEnum):
    ORDER_CONFIRMED = "order_confirmed"
    PAYMENT_CONFIRMED = "payment_confirmed"
    PAYMENT_FAILED = "payment_failed"
    CYCLE_CLOSING = "cycle_closing"
    CANCELLATION = "cancellation"
    REFUND = "refund"
    ACCOUNT_VERIFICATION = "account_verification"
    PASSWORD_RESET = "password_reset"


class NotificationStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class Notification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType, native_enum=False, length=40), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), default="email")
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, native_enum=False, length=20), default=NotificationStatus.PENDING
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship()
