import uuid
from decimal import Decimal

from pydantic import BaseModel

from app.models.payment import PaymentStatus


class InitializePaymentRequest(BaseModel):
    order_number: str


class InitializePaymentResponse(BaseModel):
    authorization_url: str
    access_code: str
    reference: str


class PaymentResponse(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    provider: str
    reference: str
    amount: Decimal
    method: str | None
    status: PaymentStatus

    model_config = {"from_attributes": True}
