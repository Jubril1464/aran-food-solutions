import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class CategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class CategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str

    model_config = {"from_attributes": True}


class ProductCreate(BaseModel):
    name: str
    category_id: uuid.UUID
    description: str | None = None
    unit: str
    price: Decimal = Field(gt=0)
    minimum_order_quantity: Decimal = Field(gt=0, default=Decimal("1"))
    is_available: bool = True
    procurement_cycle_id: uuid.UUID | None = None


class ProductUpdate(BaseModel):
    name: str | None = None
    category_id: uuid.UUID | None = None
    description: str | None = None
    unit: str | None = None
    price: Decimal | None = Field(default=None, gt=0)
    minimum_order_quantity: Decimal | None = Field(default=None, gt=0)
    is_available: bool | None = None
    procurement_cycle_id: uuid.UUID | None = None


class ProductResponse(BaseModel):
    id: uuid.UUID
    name: str
    category_id: uuid.UUID
    category: CategoryResponse | None = None
    description: str | None
    unit: str
    price: Decimal
    minimum_order_quantity: Decimal
    is_available: bool
    image_url: str | None
    procurement_cycle_id: uuid.UUID | None

    model_config = {"from_attributes": True}
