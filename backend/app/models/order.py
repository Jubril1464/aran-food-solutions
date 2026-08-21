import uuid
from enum import StrEnum

from sqlalchemy import Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class OrderStatus(StrEnum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAID = "PAID"
    CONFIRMED = "CONFIRMED"
    AGGREGATING = "AGGREGATING"
    PROCUREMENT = "PROCUREMENT"
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    PACKAGED = "PACKAGED"
    DISPATCHED = "DISPATCHED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"
    PARTIALLY_FULFILLED = "PARTIALLY_FULFILLED"
    FAILED_DELIVERY = "FAILED_DELIVERY"


# Explicit allowed-transition map. Only forward progress + the exception states
# reachable from an active order are permitted; anything else is rejected by
# app.modules.orders.service.transition_order.
ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING_PAYMENT: {OrderStatus.PAID, OrderStatus.CANCELLED},
    OrderStatus.PAID: {OrderStatus.CONFIRMED, OrderStatus.REFUNDED, OrderStatus.CANCELLED},
    OrderStatus.CONFIRMED: {OrderStatus.AGGREGATING, OrderStatus.CANCELLED, OrderStatus.REFUNDED},
    OrderStatus.AGGREGATING: {OrderStatus.PROCUREMENT, OrderStatus.CANCELLED, OrderStatus.REFUNDED},
    OrderStatus.PROCUREMENT: {OrderStatus.RECEIVED, OrderStatus.PARTIALLY_FULFILLED, OrderStatus.CANCELLED},
    OrderStatus.RECEIVED: {OrderStatus.PROCESSING, OrderStatus.PARTIALLY_FULFILLED},
    OrderStatus.PROCESSING: {OrderStatus.PACKAGED, OrderStatus.PARTIALLY_FULFILLED},
    OrderStatus.PACKAGED: {OrderStatus.DISPATCHED},
    OrderStatus.DISPATCHED: {OrderStatus.DELIVERED, OrderStatus.FAILED_DELIVERY},
    OrderStatus.FAILED_DELIVERY: {OrderStatus.DISPATCHED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
    OrderStatus.REFUNDED: set(),
    OrderStatus.PARTIALLY_FULFILLED: {OrderStatus.PROCESSING, OrderStatus.PACKAGED},
}


class Order(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "orders"

    order_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    delivery_address_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("addresses.id"), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False, length=30), default=OrderStatus.PENDING_PAYMENT, nullable=False
    )
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    delivery_fee: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    service_fee: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    status_history: Mapped[list["OrderStatusHistory"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderStatusHistory.created_at"
    )
    payments: Mapped[list["Payment"]] = relationship(back_populates="order")


class OrderItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("products.id"), nullable=False)
    procurement_cycle_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("procurement_cycles.id"), nullable=False
    )
    quantity: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    line_total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()
    procurement_cycle: Mapped["ProcurementCycle"] = relationship()


class OrderStatusHistory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "order_status_history"

    order_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus, native_enum=False, length=30), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    order: Mapped[Order] = relationship(back_populates="status_history")
