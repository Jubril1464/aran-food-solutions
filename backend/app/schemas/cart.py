import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.product import ProductResponse


class CartItemCreate(BaseModel):
    product_id: uuid.UUID
    quantity: Decimal = Field(gt=0)


class CartItemUpdate(BaseModel):
    quantity: Decimal = Field(gt=0)


class CartItemResponse(BaseModel):
    id: uuid.UUID
    product: ProductResponse
    quantity: Decimal
    line_total: Decimal

    model_config = {"from_attributes": True}


class CartResponse(BaseModel):
    id: uuid.UUID
    items: list[CartItemResponse]
    subtotal: Decimal
    delivery_fee: Decimal
    service_fee: Decimal
    total: Decimal
