import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.user import UserRole
from app.schemas.order import OrderResponse


class AddressCreate(BaseModel):
    label: str = "Home"
    street: str
    city: str
    state: str
    phone_number: str
    is_default: bool = False


class AddressUpdate(BaseModel):
    label: str | None = None
    street: str | None = None
    city: str | None = None
    state: str | None = None
    phone_number: str | None = None
    is_default: bool | None = None


class AddressResponse(BaseModel):
    id: uuid.UUID
    label: str
    street: str
    city: str
    state: str
    phone_number: str
    is_default: bool

    model_config = {"from_attributes": True}


class CustomerSummaryResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    phone_number: str
    business_name: str | None
    is_active: bool
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CustomerListResponse(BaseModel):
    customers: list[CustomerSummaryResponse]
    total: int
    page: int
    page_size: int


class CustomerDetailResponse(CustomerSummaryResponse):
    addresses: list[AddressResponse]
    orders: list[OrderResponse]


class SetActiveRequest(BaseModel):
    is_active: bool
