from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import get_settings
from app.core.logging import RequestContextMiddleware, configure_logging, logger
from app.core.queue import redeliver_pending
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
    # Sweep up notifications a previous process enqueued but never delivered.
    # With in-process delivery a background task dies with its process, and a
    # free-tier host stops the service whenever it goes idle, so this is what
    # keeps "enqueued moments before a restart" from meaning "lost".
    # Deliberately non-fatal: a database that isn't reachable yet must not stop
    # the app from starting and reporting itself unhealthy.
    try:
        await redeliver_pending()
    except Exception:
        logger.exception("pending_notification_sweep_failed")
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# slowapi's default storage is in-process, so limits are per instance. That is
# exactly right while this runs as a single web service, and would need a shared
# Redis counter only if it were ever scaled out horizontally.
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

# Uploaded files are served by the app itself when using local-disk storage.
# The directory is created rather than assumed: StaticFiles raises at import time
# if it's missing, which would turn a fresh checkout - or a host with an empty
# filesystem - into an app that won't start at all.
#
# Note that on a host without a persistent disk, local uploads survive only until
# the next deploy or restart. Point STORAGE_BACKEND at any S3-compatible bucket
# to make them durable (see app/core/storage.py).
if settings.storage_backend == "local":
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
