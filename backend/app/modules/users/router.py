import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin, require_customer
from app.models.user import User
from app.modules.orders.service import to_order_response
from app.modules.users import service
from app.schemas.user import (
    AddressCreate,
    AddressResponse,
    AddressUpdate,
    CustomerDetailResponse,
    CustomerListResponse,
    SetActiveRequest,
)

router = APIRouter(prefix="/users", tags=["users"])
admin_router = APIRouter(prefix="/admin/customers", tags=["admin:customers"], dependencies=[Depends(require_admin)])


@router.get("/addresses", response_model=list[AddressResponse])
async def list_addresses(user: User = Depends(require_customer), db: AsyncSession = Depends(get_db)):
    return await service.list_addresses(db, user)


@router.post("/addresses", response_model=AddressResponse, status_code=201)
async def create_address(data: AddressCreate, user: User = Depends(require_customer), db: AsyncSession = Depends(get_db)):
    return await service.create_address(db, user, data)


@router.patch("/addresses/{address_id}", response_model=AddressResponse)
async def update_address(
    address_id: uuid.UUID,
    data: AddressUpdate,
    user: User = Depends(require_customer),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_address(db, user, address_id, data)


@router.delete("/addresses/{address_id}", status_code=204)
async def delete_address(address_id: uuid.UUID, user: User = Depends(require_customer), db: AsyncSession = Depends(get_db)):
    await service.delete_address(db, user, address_id)


@admin_router.get("", response_model=CustomerListResponse)
async def list_customers(
    search: str | None = None, page: int = 1, page_size: int = 20, db: AsyncSession = Depends(get_db)
):
    customers, total = await service.list_customers(db, search=search, page=page, page_size=page_size)
    return CustomerListResponse(customers=customers, total=total, page=page, page_size=page_size)


@admin_router.get("/{customer_id}", response_model=CustomerDetailResponse)
async def get_customer(customer_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    customer = await service.get_customer(db, customer_id)
    addresses = await service.list_addresses(db, customer)
    orders = await service.get_customer_orders(db, customer_id)
    return CustomerDetailResponse(
        **{
            "id": customer.id,
            "full_name": customer.full_name,
            "email": customer.email,
            "phone_number": customer.phone_number,
            "business_name": customer.business_name,
            "is_active": customer.is_active,
            "is_verified": customer.is_verified,
            "created_at": customer.created_at,
        },
        addresses=addresses,
        orders=[to_order_response(o) for o in orders],
    )


@admin_router.patch("/{customer_id}/active", response_model=CustomerDetailResponse)
async def set_customer_active(
    customer_id: uuid.UUID, data: SetActiveRequest, db: AsyncSession = Depends(get_db)
):
    await service.set_customer_active(db, customer_id, data.is_active)
    return await get_customer(customer_id, db)
