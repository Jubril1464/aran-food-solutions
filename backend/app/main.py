import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import get_settings
from app.core.logging import RequestContextMiddleware, configure_logging
from app.core.rate_limit import limiter
from app.modules.analytics.router import router as analytics_router
from app.modules.auth.router import router as auth_router
from app.modules.cart.router import router as cart_router
from app.modules.delivery.router import router as delivery_router
from app.modules.inventory.router import router as inventory_router
from app.modules.orders.router import admin_router as orders_admin_router
from app.modules.orders.router import router as orders_router
from app.modules.packaging.router import router as packaging_router
from app.modules.payments.router import router as payments_router
from app.modules.procurement.router import router as procurement_router
from app.modules.products.router import admin_router as products_admin_router
from app.modules.products.router import router as products_router
from app.modules.suppliers.router import router as suppliers_router
from app.modules.users.router import admin_router as users_admin_router
from app.modules.users.router import router as users_router

settings = get_settings()
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# slowapi's default storage is in-process. On Lambda that means the limits are
# enforced per execution environment rather than globally, so a burst spread
# across cold starts can exceed them; it still blocks the single-client hammering
# it's there for. A shared limiter would need Redis/ElastiCache, deliberately not
# provisioned in this design (see infra/DEPLOY.md).
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Local-disk uploads are a dev/docker-compose convenience only. On Lambda the
# filesystem is read-only apart from /tmp and is discarded with the execution
# environment, so serving uploads from it would be broken even if it mounted -
# the deployment sets STORAGE_BACKEND=s3. Guarded (rather than assumed) because
# StaticFiles raises at import time if the directory is missing, which would
# turn a misconfigured env var into a function that fails to start at all.
if settings.storage_backend == "local" and not os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    Path(settings.local_storage_path).mkdir(parents=True, exist_ok=True)
    app.mount(settings.local_storage_public_url, StaticFiles(directory=settings.local_storage_path), name="uploads")

api = settings.api_prefix

# Priority 1 — customer-facing
app.include_router(auth_router, prefix=api)
app.include_router(users_router, prefix=api)
app.include_router(products_router, prefix=api)
app.include_router(cart_router, prefix=api)
app.include_router(orders_router, prefix=api)
app.include_router(payments_router, prefix=api)

# Priority 2 — admin
app.include_router(products_admin_router, prefix=api)
app.include_router(users_admin_router, prefix=api)
app.include_router(procurement_router, prefix=api)
app.include_router(orders_admin_router, prefix=api)
app.include_router(analytics_router, prefix=api)

# Future phases — stub routers only
app.include_router(suppliers_router, prefix=api)
app.include_router(inventory_router, prefix=api)
app.include_router(packaging_router, prefix=api)
app.include_router(delivery_router, prefix=api)


@app.get("/health")
async def health():
    return {"status": "ok"}
