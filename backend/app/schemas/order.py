import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.order import OrderStatus


class CheckoutRequest(BaseModel):
    delivery_address_id: uuid.UUID
    payment_method: str = "paystack"


class OrderItemResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal
    procurement_cycle_id: uuid.UUID

    model_config = {"from_attributes": True}


class OrderStatusHistoryEntry(BaseModel):
    status: OrderStatus
    note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: uuid.UUID
    order_number: str
    status: OrderStatus
    subtotal: Decimal
    delivery_fee: Decimal
    service_fee: Decimal
    total: Decimal
    created_at: datetime
    items: list[OrderItemResponse]

    model_config = {"from_attributes": True}


class OrderDetailResponse(OrderResponse):
    status_history: list[OrderStatusHistoryEntry]


class OrderListResponse(BaseModel):
    orders: list[OrderResponse]
    total: int
