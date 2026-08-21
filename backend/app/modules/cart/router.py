import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_customer
from app.models.user import User
from app.modules.cart import service
from app.schemas.cart import CartItemCreate, CartItemUpdate, CartResponse

router = APIRouter(prefix="/cart", tags=["cart"])


@router.get("", response_model=CartResponse)
async def get_cart(user: User = Depends(require_customer), db: AsyncSession = Depends(get_db)):
    cart = await service.get_or_create_cart(db, user)
    return service.to_cart_response(cart)


@router.post("/items", response_model=CartResponse)
async def add_item(data: CartItemCreate, user: User = Depends(require_customer), db: AsyncSession = Depends(get_db)):
    cart = await service.add_item(db, user, data)
    return service.to_cart_response(cart)


@router.patch("/items/{item_id}", response_model=CartResponse)
async def update_item(
    item_id: uuid.UUID,
    data: CartItemUpdate,
    user: User = Depends(require_customer),
    db: AsyncSession = Depends(get_db),
):
    cart = await service.update_item(db, user, item_id, data)
    return service.to_cart_response(cart)


@router.delete("/items/{item_id}", response_model=CartResponse)
async def remove_item(item_id: uuid.UUID, user: User = Depends(require_customer), db: AsyncSession = Depends(get_db)):
    cart = await service.remove_item(db, user, item_id)
    return service.to_cart_response(cart)
