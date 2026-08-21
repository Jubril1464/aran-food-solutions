import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.audit import log_admin_action
from app.core.utils import slugify
from app.models.product import Category, Product
from app.models.user import User
from app.schemas.product import CategoryCreate, ProductCreate, ProductUpdate


async def list_categories(db: AsyncSession) -> list[Category]:
    result = await db.execute(select(Category).order_by(Category.name))
    return list(result.scalars().all())


async def create_category(db: AsyncSession, data: CategoryCreate) -> Category:
    category = Category(name=data.name, slug=slugify(data.name))
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


async def list_products(
    db: AsyncSession, *, category_id: uuid.UUID | None, available_only: bool, search: str | None
) -> list[Product]:
    query = select(Product).options(selectinload(Product.category))
    if category_id:
        query = query.where(Product.category_id == category_id)
    if available_only:
        query = query.where(Product.is_available.is_(True))
    if search:
        query = query.where(Product.name.ilike(f"%{search}%"))
    result = await db.execute(query.order_by(Product.name))
    return list(result.scalars().all())


async def get_product(db: AsyncSession, product_id: uuid.UUID) -> Product:
    product = (
        await db.execute(
            select(Product).where(Product.id == product_id).options(selectinload(Product.category))
        )
    ).scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


async def create_product(db: AsyncSession, admin: User, data: ProductCreate) -> Product:
    product = Product(**data.model_dump())
    db.add(product)
    await db.flush()
    await log_admin_action(
        db, admin_user=admin, action="create_product", entity_type="product", entity_id=str(product.id),
        after=data.model_dump(mode="json"),
    )
    await db.commit()
    await db.refresh(product, attribute_names=["category"])
    return product


async def update_product(db: AsyncSession, admin: User, product_id: uuid.UUID, data: ProductUpdate) -> Product:
    product = await get_product(db, product_id)
    before = {"price": str(product.price), "is_available": product.is_available}
    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(product, field, value)
    await log_admin_action(
        db, admin_user=admin, action="update_product", entity_type="product", entity_id=str(product.id),
        before=before, after={k: str(v) for k, v in updates.items()},
    )
    await db.commit()
    await db.refresh(product, attribute_names=["category"])
    return product


async def delete_product(db: AsyncSession, admin: User, product_id: uuid.UUID) -> None:
    product = await get_product(db, product_id)
    await log_admin_action(
        db, admin_user=admin, action="delete_product", entity_type="product", entity_id=str(product.id),
        before={"name": product.name},
    )
    await db.delete(product)
    await db.commit()


async def set_product_image(db: AsyncSession, admin: User, product_id: uuid.UUID, image_url: str) -> Product:
    product = await get_product(db, product_id)
    product.image_url = image_url
    await db.commit()
    await db.refresh(product, attribute_names=["category"])
    return product
