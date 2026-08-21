import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.audit import log_admin_action
from app.models.notification import NotificationType
from app.models.order import Order, OrderItem, OrderStatus, OrderStatusHistory
from app.models.procurement import CycleStatus, ProcurementCycle, ProcurementItem
from app.models.product import Product
from app.models.user import User
from app.modules.notifications.service import notify
from app.schemas.procurement import ProcurementCycleCreate, ProcurementCycleUpdate


async def list_cycles(db: AsyncSession) -> list[ProcurementCycle]:
    result = await db.execute(select(ProcurementCycle).order_by(ProcurementCycle.order_window_opens_at.desc()))
    return list(result.scalars().all())


async def get_cycle(db: AsyncSession, cycle_id: uuid.UUID) -> ProcurementCycle:
    cycle = (
        await db.execute(select(ProcurementCycle).where(ProcurementCycle.id == cycle_id))
    ).scalar_one_or_none()
    if cycle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Procurement cycle not found")
    return cycle


async def create_cycle(db: AsyncSession, admin: User, data: ProcurementCycleCreate) -> ProcurementCycle:
    if data.order_window_closes_at <= data.order_window_opens_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Close time must be after open time")
    cycle = ProcurementCycle(**data.model_dump())
    db.add(cycle)
    await db.flush()
    await log_admin_action(
        db, admin_user=admin, action="create_cycle", entity_type="procurement_cycle", entity_id=str(cycle.id)
    )
    await db.commit()
    await db.refresh(cycle)
    return cycle


async def update_cycle(
    db: AsyncSession, admin: User, cycle_id: uuid.UUID, data: ProcurementCycleUpdate
) -> ProcurementCycle:
    cycle = await get_cycle(db, cycle_id)
    if cycle.status != CycleStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only draft cycles can be edited")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(cycle, field, value)
    await db.commit()
    await db.refresh(cycle)
    return cycle


async def _active_open_cycle_for_category(
    db: AsyncSession, category_id: uuid.UUID | None, exclude_cycle_id: uuid.UUID | None = None
) -> ProcurementCycle | None:
    query = select(ProcurementCycle).where(
        ProcurementCycle.status == CycleStatus.OPEN, ProcurementCycle.category_id == category_id
    )
    if exclude_cycle_id:
        query = query.where(ProcurementCycle.id != exclude_cycle_id)
    return (await db.execute(query)).scalar_one_or_none()


async def open_cycle(db: AsyncSession, admin: User, cycle_id: uuid.UUID) -> ProcurementCycle:
    cycle = await get_cycle(db, cycle_id)
    if cycle.status != CycleStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only draft cycles can be opened")
    conflicting = await _active_open_cycle_for_category(db, cycle.category_id, exclude_cycle_id=cycle.id)
    if conflicting is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another cycle is already open for this category. Close it before opening a new one.",
        )
    cycle.status = CycleStatus.OPEN
    await log_admin_action(
        db, admin_user=admin, action="open_cycle", entity_type="procurement_cycle", entity_id=str(cycle.id)
    )
    await db.commit()
    await db.refresh(cycle)
    return cycle


def _as_aware(dt: datetime) -> datetime:
    # SQLite (used in tests) does not persist tzinfo even for DateTime(timezone=True)
    # columns and always returns naive datetimes; Postgres returns aware ones. Treat
    # any naive value read back from the DB as UTC so comparisons work on both.
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


async def get_active_cycle_for_product(db: AsyncSession, product: Product) -> ProcurementCycle | None:
    """Resolve the cycle an order line item should attach to: the product's assigned
    cycle if it's open and within its order window, else the open cycle for its category."""
    now = datetime.now(timezone.utc)

    if product.procurement_cycle_id:
        cycle = await get_cycle(db, product.procurement_cycle_id)
        if (
            cycle.status == CycleStatus.OPEN
            and _as_aware(cycle.order_window_opens_at) <= now <= _as_aware(cycle.order_window_closes_at)
        ):
            return cycle
        return None

    cycle = await _active_open_cycle_for_category(db, product.category_id)
    if cycle and _as_aware(cycle.order_window_opens_at) <= now <= _as_aware(cycle.order_window_closes_at):
        return cycle
    return None


async def compute_aggregation(db: AsyncSession, cycle_id: uuid.UUID) -> list[tuple[Product, float]]:
    rows = (
        await db.execute(
            select(OrderItem.product_id, func.sum(OrderItem.quantity))
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                OrderItem.procurement_cycle_id == cycle_id,
                Order.status.not_in([OrderStatus.CANCELLED, OrderStatus.PENDING_PAYMENT]),
            )
            .group_by(OrderItem.product_id)
        )
    ).all()
    results = []
    for product_id, total_qty in rows:
        product = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one()
        results.append((product, total_qty))
    return results


async def get_aggregation_report(db: AsyncSession, cycle_id: uuid.UUID) -> tuple[ProcurementCycle, list[tuple[Product, float]]]:
    cycle = await get_cycle(db, cycle_id)
    lines = await compute_aggregation(db, cycle_id)
    return cycle, lines


async def close_cycle(db: AsyncSession, admin: User, cycle_id: uuid.UUID) -> ProcurementCycle:
    cycle = await get_cycle(db, cycle_id)
    if cycle.status != CycleStatus.OPEN:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only open cycles can be closed")

    cycle.status = CycleStatus.CLOSED

    # Persist the aggregation snapshot.
    await db.execute(ProcurementItem.__table__.delete().where(ProcurementItem.cycle_id == cycle.id))
    lines = await compute_aggregation(db, cycle.id)
    for product, total_qty in lines:
        db.add(ProcurementItem(cycle_id=cycle.id, product_id=product.id, total_quantity=total_qty))

    # Transition orders that belong entirely to this cycle: CONFIRMED -> AGGREGATING -> PROCUREMENT.
    orders_result = await db.execute(
        select(Order)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .where(OrderItem.procurement_cycle_id == cycle.id, Order.status == OrderStatus.CONFIRMED)
        .options(selectinload(Order.items))
        .distinct()
    )
    orders = list(orders_result.scalars().all())
    fully_in_cycle_orders = [o for o in orders if all(i.procurement_cycle_id == cycle.id for i in o.items)]

    for order in fully_in_cycle_orders:
        for new_status in (OrderStatus.AGGREGATING, OrderStatus.PROCUREMENT):
            order.status = new_status
            db.add(OrderStatusHistory(order_id=order.id, status=new_status, note=f"Cycle '{cycle.name}' closed"))
        user = (await db.execute(select(User).where(User.id == order.user_id))).scalar_one()
        await notify(
            db,
            user=user,
            notification_type=NotificationType.CYCLE_CLOSING,
            payload={"cycle_name": cycle.name, "order_number": order.order_number},
        )

    await log_admin_action(
        db, admin_user=admin, action="close_cycle", entity_type="procurement_cycle", entity_id=str(cycle.id),
        after={"orders_transitioned": len(fully_in_cycle_orders)},
    )
    await db.commit()
    await db.refresh(cycle)
    return cycle
