import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.audit import log_admin_action
from app.core.config import get_settings
from app.core.utils import generate_order_number
from app.models.notification import NotificationType
from app.models.order import ALLOWED_TRANSITIONS, Order, OrderItem, OrderStatus, OrderStatusHistory
from app.models.product import Product
from app.models.user import Address, User, UserRole
from app.modules.cart.service import get_or_create_cart
from app.modules.notifications.service import notify
from app.modules.procurement.service import get_active_cycle_for_product
from app.schemas.order import CheckoutRequest, OrderDetailResponse, OrderItemResponse, OrderResponse, OrderStatusHistoryEntry

settings = get_settings()


def _order_query():
    return select(Order).options(
        selectinload(Order.items).selectinload(OrderItem.product),
        selectinload(Order.items).selectinload(OrderItem.procurement_cycle),
        selectinload(Order.status_history),
    )


async def transition_order(db: AsyncSession, order: Order, new_status: OrderStatus, note: str | None = None) -> None:
    allowed = ALLOWED_TRANSITIONS.get(order.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot transition order from {order.status} to {new_status}",
        )
    order.status = new_status
    db.add(OrderStatusHistory(order_id=order.id, status=new_status, note=note))


async def checkout(db: AsyncSession, user: User, data: CheckoutRequest) -> Order:
    cart = await get_or_create_cart(db, user)
    if not cart.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty")

    address = (
        await db.execute(select(Address).where(Address.id == data.delivery_address_id, Address.user_id == user.id))
    ).scalar_one_or_none()
    if address is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Delivery address not found")

    order_items_data = []
    subtotal = Decimal("0")
    for cart_item in cart.items:
        product = (await db.execute(select(Product).where(Product.id == cart_item.product_id))).scalar_one_or_none()
        if product is None or not product.is_available:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Product no longer available")
        if cart_item.quantity < product.minimum_order_quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Minimum order quantity for {product.name} is {product.minimum_order_quantity} {product.unit}",
            )
        cycle = await get_active_cycle_for_product(db, product)
        if cycle is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No active procurement cycle is open for {product.name} right now",
            )
        item_total = (Decimal(cart_item.quantity) * Decimal(product.price)).quantize(Decimal("0.01"))
        subtotal += item_total
        order_items_data.append((product, cycle, cart_item.quantity, item_total))

    delivery_fee = Decimal(str(settings.delivery_fee))
    service_fee = (subtotal * Decimal(str(settings.service_fee_percent)) / Decimal("100")).quantize(Decimal("0.01"))
    total = subtotal + delivery_fee + service_fee

    order = Order(
        order_number=generate_order_number(),
        user_id=user.id,
        delivery_address_id=address.id,
        status=OrderStatus.PENDING_PAYMENT,
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        service_fee=service_fee,
        total=total,
    )
    db.add(order)
    await db.flush()

    for product, cycle, quantity, line_total in order_items_data:
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                procurement_cycle_id=cycle.id,
                quantity=quantity,
                unit_price=product.price,
                line_total=line_total,
            )
        )
    db.add(OrderStatusHistory(order_id=order.id, status=OrderStatus.PENDING_PAYMENT, note="Order created"))

    for cart_item in list(cart.items):
        await db.delete(cart_item)

    await db.commit()
    return await get_order_by_id(db, order.id)


async def get_order_by_id(db: AsyncSession, order_id: uuid.UUID) -> Order:
    order = (await db.execute(_order_query().where(Order.id == order_id))).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


async def get_order_by_number(db: AsyncSession, order_number: str, owner: User | None = None) -> Order:
    order = (
        await db.execute(_order_query().where(Order.order_number == order_number))
    ).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if owner is not None and owner.role != UserRole.ADMIN and order.user_id != owner.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


async def list_orders_for_user(
    db: AsyncSession, user: User, *, status_filter: OrderStatus | None, sort: str
) -> list[Order]:
    query = _order_query().where(Order.user_id == user.id)
    if status_filter:
        query = query.where(Order.status == status_filter)
    order_col = Order.created_at.desc() if sort == "-created_at" else Order.created_at.asc()
    query = query.order_by(order_col)
    result = await db.execute(query)
    return list(result.scalars().unique().all())


async def list_all_orders(db: AsyncSession, *, status_filter: OrderStatus | None) -> list[Order]:
    query = _order_query()
    if status_filter:
        query = query.where(Order.status == status_filter)
    result = await db.execute(query.order_by(Order.created_at.desc()))
    return list(result.scalars().unique().all())


async def cancel_order(db: AsyncSession, admin: User, order_number: str, refund: bool) -> Order:
    order = await get_order_by_number(db, order_number)
    new_status = OrderStatus.REFUNDED if refund else OrderStatus.CANCELLED
    await transition_order(db, order, new_status, note=f"Cancelled by admin {admin.email}")
    await log_admin_action(
        db, admin_user=admin, action="cancel_order", entity_type="order", entity_id=str(order.id),
        after={"status": new_status.value},
    )
    user = (await db.execute(select(User).where(User.id == order.user_id))).scalar_one()
    await notify(
        db,
        user=user,
        notification_type=NotificationType.REFUND if refund else NotificationType.CANCELLATION,
        payload={"order_number": order.order_number},
    )
    await db.commit()
    return await get_order_by_id(db, order.id)


def to_order_response(order: Order) -> OrderResponse:
    return OrderResponse(
        id=order.id,
        order_number=order.order_number,
        status=order.status,
        subtotal=order.subtotal,
        delivery_fee=order.delivery_fee,
        service_fee=order.service_fee,
        total=order.total,
        created_at=order.created_at,
        items=[
            OrderItemResponse(
                id=item.id,
                product_id=item.product_id,
                product_name=item.product.name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                line_total=item.line_total,
                procurement_cycle_id=item.procurement_cycle_id,
            )
            for item in order.items
        ],
    )


def to_order_detail_response(order: Order) -> OrderDetailResponse:
    base = to_order_response(order)
    return OrderDetailResponse(
        **base.model_dump(),
        status_history=[
            OrderStatusHistoryEntry(status=h.status, note=h.note, created_at=h.created_at)
            for h in order.status_history
        ],
    )
