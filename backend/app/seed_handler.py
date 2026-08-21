"""Bootstrap Lambda entrypoint: creates the first admin user, and optionally a
starter catalogue with an open procurement cycle.

Invoked by hand once after the first deploy (and safely re-invokable):

    aws lambda invoke --function-name agric-prod-seed /dev/stdout

Why this exists: /auth/register always creates a CUSTOMER, by design - there is
no self-service route to an admin account and there shouldn't be. Without a
bootstrap step a freshly deployed environment has no admin, so no products, no
categories and no procurement cycle can be created, and the customer flow
dead-ends on an empty catalogue. Rather than reaching into the database by hand,
this runs the same models the app runs, in the same image.

Credentials come from the function's environment (set by
infra/terraform/lambda.tf from `admin_email`/`admin_password`, the latter
generated if not supplied) so no password is ever typed into a shell or passed
in an invoke payload. The password is never logged or returned.

Everything here is idempotent: re-invoking promotes/repairs rather than
duplicating, and refreshes a demo cycle whose order window has expired - which
is what makes it safe to re-run before a demo weeks later.

Deliberately NOT written to the admin audit log: this is a deployment
bootstrap, not an action an administrator took in the app.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.logging import configure_logging, logger
from app.core.security import hash_password
from app.models.procurement import CycleStatus, ProcurementCycle
from app.models.product import Category, Product
from app.models.user import User, UserRole

settings = get_settings()

# A small, deliberately plausible Nigerian commodity catalogue: enough to show
# the catalogue, cart, MOQ enforcement, checkout and aggregation working, and no
# more. Prices are illustrative demo figures in NGN, not researched market rates.
# One product carries an MOQ above 1 so the add-to-cart minimum is visible.
DEMO_CATALOGUE: list[dict] = [
    {
        "category": "Grains & Cereals",
        "slug": "grains-cereals",
        "products": [
            {
                "name": "Long Grain Rice (50kg bag)",
                "unit": "bag",
                "price": Decimal("85000.00"),
                "minimum_order_quantity": Decimal("1"),
                "description": "Parboiled long grain rice, 50kg bag. Pooled directly from mill-level bulk purchase.",
            },
            {
                "name": "Yellow Maize (100kg bag)",
                "unit": "bag",
                "price": Decimal("62000.00"),
                "minimum_order_quantity": Decimal("2"),
                "description": "Dried yellow maize, 100kg bag. Minimum two bags per order at this tier.",
            },
            {
                "name": "Millet (50kg bag)",
                "unit": "bag",
                "price": Decimal("48000.00"),
                "minimum_order_quantity": Decimal("1"),
                "description": "Cleaned millet, 50kg bag.",
            },
        ],
    },
    {
        "category": "Legumes & Beans",
        "slug": "legumes-beans",
        "products": [
            {
                "name": "Brown Beans (50kg bag)",
                "unit": "bag",
                "price": Decimal("97000.00"),
                "minimum_order_quantity": Decimal("1"),
                "description": "Oloyin brown beans, 50kg bag, hand-sorted.",
            },
            {
                "name": "Groundnuts (25kg bag)",
                "unit": "bag",
                "price": Decimal("41000.00"),
                "minimum_order_quantity": Decimal("1"),
                "description": "Raw shelled groundnuts, 25kg bag.",
            },
        ],
    },
    {
        "category": "Tubers & Flour",
        "slug": "tubers-flour",
        "products": [
            {
                "name": "White Garri (50kg bag)",
                "unit": "bag",
                "price": Decimal("43000.00"),
                "minimum_order_quantity": Decimal("1"),
                "description": "Fine white garri, 50kg bag.",
            },
            {
                "name": "Yam Flour / Elubo (25kg bag)",
                "unit": "bag",
                "price": Decimal("38000.00"),
                "minimum_order_quantity": Decimal("1"),
                "description": "Stone-milled yam flour, 25kg bag.",
            },
        ],
    },
    {
        "category": "Oils",
        "slug": "oils",
        "products": [
            {
                "name": "Palm Oil (25 litre keg)",
                "unit": "keg",
                "price": Decimal("52000.00"),
                "minimum_order_quantity": Decimal("1"),
                "description": "Unrefined red palm oil, 25 litre keg.",
            },
            {
                "name": "Groundnut Oil (25 litre keg)",
                "unit": "keg",
                "price": Decimal("64000.00"),
                "minimum_order_quantity": Decimal("1"),
                "description": "Filtered groundnut oil, 25 litre keg.",
            },
        ],
    },
]

# How long a seeded order window stays open. Re-invoking the function extends an
# expired one, so a demo can be revived without touching the database.
DEMO_WINDOW = timedelta(days=14)


async def _seed_admin(db, *, email: str, password: str, phone: str, reset_password: bool) -> str:
    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing is not None:
        changed = []
        if existing.role != UserRole.ADMIN:
            existing.role = UserRole.ADMIN
            changed.append("role")
        if not existing.is_verified:
            existing.is_verified = True
            changed.append("is_verified")
        if not existing.is_active:
            existing.is_active = True
            changed.append("is_active")
        if reset_password:
            existing.password_hash = hash_password(password)
            changed.append("password")
        return "unchanged" if not changed else "repaired:" + ",".join(changed)

    db.add(
        User(
            full_name="Platform Administrator",
            phone_number=phone,
            email=email,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            # Skips the email-verification step, which would otherwise require a
            # working mailbox before the platform could be administered at all.
            is_verified=True,
            is_active=True,
        )
    )
    return "created"


async def _seed_catalogue(db) -> dict:
    now = datetime.now(timezone.utc)
    counts = {"categories_created": 0, "products_created": 0, "cycles_created": 0, "cycles_extended": 0}

    for group in DEMO_CATALOGUE:
        category = (
            await db.execute(select(Category).where(Category.slug == group["slug"]))
        ).scalar_one_or_none()
        if category is None:
            category = Category(name=group["category"], slug=group["slug"])
            db.add(category)
            await db.flush()
            counts["categories_created"] += 1

        for spec in group["products"]:
            exists = (
                await db.execute(
                    select(Product).where(Product.name == spec["name"], Product.category_id == category.id)
                )
            ).scalar_one_or_none()
            if exists is not None:
                continue
            db.add(
                Product(
                    name=spec["name"],
                    category_id=category.id,
                    description=spec["description"],
                    unit=spec["unit"],
                    price=spec["price"],
                    minimum_order_quantity=spec["minimum_order_quantity"],
                    is_available=True,
                    # Left unpinned on purpose: an unpinned product resolves the
                    # open cycle for its *category* at checkout, which is the
                    # common path (see get_active_cycle_for_product).
                    procurement_cycle_id=None,
                )
            )
            counts["products_created"] += 1

        # At most one OPEN cycle per category is allowed (open_cycle enforces it),
        # and checkout requires "now" to fall inside the window - so an expired
        # window is extended rather than left to silently break checkout.
        cycle = (
            await db.execute(
                select(ProcurementCycle).where(
                    ProcurementCycle.category_id == category.id,
                    ProcurementCycle.status == CycleStatus.OPEN,
                )
            )
        ).scalar_one_or_none()
        if cycle is None:
            db.add(
                ProcurementCycle(
                    name=f"{now:%B %Y} — {category.name}",
                    category_id=category.id,
                    order_window_opens_at=now - timedelta(hours=1),
                    order_window_closes_at=now + DEMO_WINDOW,
                    status=CycleStatus.OPEN,
                )
            )
            counts["cycles_created"] += 1
        else:
            closes_at = cycle.order_window_closes_at
            if closes_at.tzinfo is None:  # SQLite round-trips naive datetimes
                closes_at = closes_at.replace(tzinfo=timezone.utc)
            if closes_at <= now:
                cycle.order_window_closes_at = now + DEMO_WINDOW
                counts["cycles_extended"] += 1

    return counts


async def _run(event: dict) -> dict:
    email = event.get("admin_email") or settings.seed_admin_email
    password = event.get("admin_password") or settings.seed_admin_password
    phone = event.get("admin_phone") or settings.seed_admin_phone
    demo_data = event.get("demo_data", settings.seed_demo_data)
    reset_password = bool(event.get("reset_password", False))

    if not email:
        raise ValueError("No admin email configured (set SEED_ADMIN_EMAIL or pass admin_email).")
    if not password:
        raise ValueError("No admin password configured (set SEED_ADMIN_PASSWORD or pass admin_password).")

    async with AsyncSessionLocal() as db:
        admin_result = await _seed_admin(
            db, email=email, password=password, phone=phone, reset_password=reset_password
        )
        catalogue = await _seed_catalogue(db) if demo_data else {}
        await db.commit()

    return {"status": "ok", "admin_email": email, "admin": admin_result, **catalogue}


def handler(event, context):
    """`event` may override the configured values:
    {"admin_email", "admin_password", "admin_phone", "demo_data", "reset_password"}.
    Note that an invoke payload is visible in your shell history, so prefer the
    Terraform-managed environment for the password.
    """
    import asyncio

    configure_logging()
    result = asyncio.run(_run(event or {}))
    # Logs the outcome, never the credential.
    logger.info("seed_completed", **result)
    return result
