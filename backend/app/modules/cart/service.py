import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.cart import Cart, CartItem
from app.models.product import Product
from app.models.user import User
from app.schemas.cart import CartItemCreate, CartItemUpdate, CartItemResponse, CartResponse

settings = get_settings()


async def get_or_create_cart(db: AsyncSession, user: User) -> Cart:
    # populate_existing forces relationships to be reloaded even if this Cart is
    # already in the identity map with a stale (e.g. pre-mutation) items collection.
    cart = (
        await db.execute(
            select(Cart)
            .where(Cart.user_id == user.id)
            .options(selectinload(Cart.items).selectinload(CartItem.product).selectinload(Product.category))
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if cart is None:
        cart = Cart(user_id=user.id)
        db.add(cart)
        await db.commit()
        await db.refresh(cart, attribute_names=["items"])
    return cart


async def _get_product_or_404(db: AsyncSession, product_id: uuid.UUID) -> Product:
    product = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


def _validate_moq_and_availability(product: Product, quantity: Decimal) -> None:
    if not product.is_available:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{product.name} is not available")
    if quantity < product.minimum_order_quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Minimum order quantity for {product.name} is {product.minimum_order_quantity} {product.unit}",
        )


async def add_item(db: AsyncSession, user: User, data: CartItemCreate) -> Cart:
    cart = await get_or_create_cart(db, user)
    product = await _get_product_or_404(db, data.product_id)
    _validate_moq_and_availability(product, data.quantity)

    existing = next((i for i in cart.items if i.product_id == product.id), None)
    if existing:
        existing.quantity = data.quantity
    else:
        db.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=data.quantity))
    await db.commit()
    return await get_or_create_cart(db, user)


async def update_item(db: AsyncSession, user: User, item_id: uuid.UUID, data: CartItemUpdate) -> Cart:
    cart = await get_or_create_cart(db, user)
    item = next((i for i in cart.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found")
    _validate_moq_and_availability(item.product, data.quantity)
    item.quantity = data.quantity
    await db.commit()
    return await get_or_create_cart(db, user)


async def remove_item(db: AsyncSession, user: User, item_id: uuid.UUID) -> Cart:
    cart = await get_or_create_cart(db, user)
    item = next((i for i in cart.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found")
    await db.delete(item)
    await db.commit()
    return await get_or_create_cart(db, user)


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def line_total(quantity: Decimal, unit_price: Decimal) -> Decimal:
    return money(Decimal(quantity) * Decimal(unit_price))


def compute_totals(cart: Cart) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    subtotal = money(sum((line_total(item.quantity, item.product.price) for item in cart.items), Decimal("0")))
    delivery_fee = Decimal(str(settings.delivery_fee)) if cart.items else Decimal("0")
    service_fee = money(subtotal * Decimal(str(settings.service_fee_percent)) / Decimal("100"))
    total = subtotal + delivery_fee + service_fee
    return subtotal, delivery_fee, service_fee, total


def to_cart_response(cart: Cart) -> CartResponse:
    subtotal, delivery_fee, service_fee, total = compute_totals(cart)
    items = [
        CartItemResponse(
            id=item.id,
            product=item.product,
            quantity=item.quantity,
            line_total=line_total(item.quantity, item.product.price),
        )
        for item in cart.items
    ]
    return CartResponse(
        id=cart.id, items=items, subtotal=subtotal, delivery_fee=delivery_fee, service_fee=service_fee, total=total
    )
