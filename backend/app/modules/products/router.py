import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import require_admin
from app.core.storage import get_storage_backend
from app.models.user import User
from app.modules.products import service
from app.schemas.product import (
    CategoryCreate,
    CategoryResponse,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)

settings = get_settings()

router = APIRouter(tags=["products"])
admin_router = APIRouter(prefix="/admin", tags=["admin:products"], dependencies=[Depends(require_admin)])


@router.get("/categories", response_model=list[CategoryResponse])
async def get_categories(db: AsyncSession = Depends(get_db)):
    return await service.list_categories(db)


@router.get("/products", response_model=list[ProductResponse])
async def get_products(
    category_id: uuid.UUID | None = None,
    available_only: bool = False,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await service.list_products(db, category_id=category_id, available_only=available_only, search=search)


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await service.get_product(db, product_id)


@admin_router.post("/categories", response_model=CategoryResponse, status_code=201)
async def create_category(data: CategoryCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_category(db, data)


@admin_router.post("/products", response_model=ProductResponse, status_code=201)
async def create_product(data: ProductCreate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await service.create_product(db, admin, data)


@admin_router.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: uuid.UUID,
    data: ProductUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_product(db, admin, product_id, data)


@admin_router.delete("/products/{product_id}", status_code=204)
async def delete_product(product_id: uuid.UUID, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    await service.delete_product(db, admin, product_id)


@admin_router.post("/products/{product_id}/image", response_model=ProductResponse)
async def upload_product_image(
    product_id: uuid.UUID,
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    # Rejected here with a clear error rather than at the gateway: API Gateway
    # caps a request at 10 MB and Lambda at a 6 MB synchronous payload, and the
    # body reaches the function base64-encoded (~33% larger), so an oversized
    # upload otherwise dies upstream as an opaque 413/502 with nothing in the
    # app's logs. See max_upload_size_mb in app/core/config.py.
    max_bytes = int(settings.max_upload_size_mb * 1024 * 1024)
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image is too large ({len(content) / 1024 / 1024:.1f} MB); the limit is {settings.max_upload_size_mb:g} MB.",
        )
    storage = get_storage_backend()
    url = await storage.save(file.filename or "upload", content, file.content_type or "application/octet-stream")
    return await service.set_product_image(db, admin, product_id, url)
