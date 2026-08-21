from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin, require_customer
from app.models.order import OrderStatus
from app.models.user import User
from app.modules.orders import service
from app.schemas.order import CheckoutRequest, OrderDetailResponse, OrderListResponse, OrderResponse

router = APIRouter(prefix="/orders", tags=["orders"])
admin_router = APIRouter(prefix="/admin/orders", tags=["admin:orders"], dependencies=[Depends(require_admin)])


@router.post("/checkout", response_model=OrderDetailResponse, status_code=201)
async def checkout(data: CheckoutRequest, user: User = Depends(require_customer), db: AsyncSession = Depends(get_db)):
    order = await service.checkout(db, user, data)
    return service.to_order_detail_response(order)


@router.get("", response_model=OrderListResponse)
async def order_history(
    status_filter: OrderStatus | None = Query(default=None, alias="status"),
    sort: str = Query(default="-created_at"),
    user: User = Depends(require_customer),
    db: AsyncSession = Depends(get_db),
):
    orders = await service.list_orders_for_user(db, user, status_filter=status_filter, sort=sort)
    responses = [service.to_order_response(o) for o in orders]
    return OrderListResponse(orders=responses, total=len(responses))


@router.get("/{order_number}", response_model=OrderDetailResponse)
async def get_order(order_number: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    order = await service.get_order_by_number(db, order_number, owner=user)
    return service.to_order_detail_response(order)


@admin_router.get("", response_model=OrderListResponse)
async def admin_list_orders(
    status_filter: OrderStatus | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
):
    orders = await service.list_all_orders(db, status_filter=status_filter)
    responses = [service.to_order_response(o) for o in orders]
    return OrderListResponse(orders=responses, total=len(responses))


@admin_router.post("/{order_number}/cancel", response_model=OrderDetailResponse)
async def admin_cancel_order(
    order_number: str, refund: bool = False, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    order = await service.cancel_order(db, admin, order_number, refund)
    return service.to_order_detail_response(order)
