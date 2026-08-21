import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.user import Address, User, UserRole
from app.schemas.user import AddressCreate, AddressUpdate


async def list_addresses(db: AsyncSession, user: User) -> list[Address]:
    result = await db.execute(select(Address).where(Address.user_id == user.id).order_by(Address.created_at))
    return list(result.scalars().all())


async def create_address(db: AsyncSession, user: User, data: AddressCreate) -> Address:
    if data.is_default:
        await db.execute(
            Address.__table__.update().where(Address.user_id == user.id).values(is_default=False)
        )
    address = Address(user_id=user.id, **data.model_dump())
    db.add(address)
    await db.commit()
    await db.refresh(address)
    return address


async def _get_owned_address(db: AsyncSession, user: User, address_id: uuid.UUID) -> Address:
    address = (
        await db.execute(select(Address).where(Address.id == address_id, Address.user_id == user.id))
    ).scalar_one_or_none()
    if address is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")
    return address


async def update_address(db: AsyncSession, user: User, address_id: uuid.UUID, data: AddressUpdate) -> Address:
    address = await _get_owned_address(db, user, address_id)
    updates = data.model_dump(exclude_unset=True)
    if updates.get("is_default"):
        await db.execute(
            Address.__table__.update().where(Address.user_id == user.id).values(is_default=False)
        )
    for field, value in updates.items():
        setattr(address, field, value)
    await db.commit()
    await db.refresh(address)
    return address


async def delete_address(db: AsyncSession, user: User, address_id: uuid.UUID) -> None:
    address = await _get_owned_address(db, user, address_id)
    await db.delete(address)
    await db.commit()


# --- Admin customer management ---


async def list_customers(db: AsyncSession, *, search: str | None, page: int, page_size: int):
    query = select(User).where(User.role == UserRole.CUSTOMER)
    if search:
        like = f"%{search}%"
        query = query.where(
            or_(User.full_name.ilike(like), User.email.ilike(like), User.phone_number.ilike(like))
        )
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    result = await db.execute(query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    return list(result.scalars().all()), total


async def get_customer(db: AsyncSession, customer_id: uuid.UUID) -> User:
    user = (
        await db.execute(select(User).where(User.id == customer_id, User.role == UserRole.CUSTOMER))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return user


async def get_customer_orders(db: AsyncSession, customer_id: uuid.UUID) -> list[Order]:
    from app.modules.orders.service import _order_query

    result = await db.execute(
        _order_query().where(Order.user_id == customer_id).order_by(Order.created_at.desc())
    )
    return list(result.scalars().unique().all())


async def set_customer_active(db: AsyncSession, customer_id: uuid.UUID, is_active: bool) -> User:
    user = await get_customer(db, customer_id)
    user.is_active = is_active
    await db.commit()
    await db.refresh(user)
    return user
