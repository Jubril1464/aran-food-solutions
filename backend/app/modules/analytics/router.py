"""Full analytics/KPIs (FR-020, PRD §21) are a future phase. This router only
exposes the basic counts explicitly listed in the MVP scope (PRD §23)."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.order import Order, OrderStatus
from app.models.procurement import CycleStatus, ProcurementCycle
from app.models.product import Product
from app.models.user import User, UserRole

router = APIRouter(prefix="/admin/analytics", tags=["admin:analytics"], dependencies=[Depends(require_admin)])


@router.get("/summary")
async def summary(db: AsyncSession = Depends(get_db)):
    customer_count = (
        await db.execute(select(func.count()).select_from(User).where(User.role == UserRole.CUSTOMER))
    ).scalar_one()
    product_count = (await db.execute(select(func.count()).select_from(Product))).scalar_one()
    order_count = (await db.execute(select(func.count()).select_from(Order))).scalar_one()
    active_cycle_count = (
        await db.execute(select(func.count()).select_from(ProcurementCycle).where(ProcurementCycle.status == CycleStatus.OPEN))
    ).scalar_one()
    orders_awaiting_payment = (
        await db.execute(select(func.count()).select_from(Order).where(Order.status == OrderStatus.PENDING_PAYMENT))
    ).scalar_one()
    total_gmv = (
        await db.execute(
            select(func.coalesce(func.sum(Order.total), 0)).where(Order.status != OrderStatus.CANCELLED)
        )
    ).scalar_one()

    return {
        "customers": customer_count,
        "products": product_count,
        "orders": order_count,
        "orders_awaiting_payment": orders_awaiting_payment,
        "active_procurement_cycles": active_cycle_count,
        "gmv": str(total_gmv),
    }
