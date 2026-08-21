"""Bootstrap: creates the first admin user, and optionally a starter catalogue
with an open procurement cycle.

    python -m app.seed              # uses SEED_* environment variables
    python -m app.seed --reset-password
    python -m app.seed --no-demo-data

Runs as part of the deploy start command (see render.yaml), and can be run by
hand any time.

Why this exists: /auth/register always creates a CUSTOMER, by design - there is
no self-service route to an admin account and there shouldn't be. Without a
bootstrap step a freshly deployed environment has no admin, so no products, no
categories and no procurement cycle can be created, and the customer flow
dead-ends on an empty catalogue. Rather than reaching into the database by hand,
this runs the same models the app runs.

Credentials come from the environment (SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD),
never from command-line arguments, so the password stays out of shell history
and process listings. It is never logged or printed.

Everything here is idempotent: re-running promotes/repairs rather than
duplicating, and refreshes a demo cycle whose order window has expired - which
is what makes it safe to run on every deploy, and to re-run before a demo weeks
later.

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


async def run(*, demo_data: bool | None = None, reset_password: bool = False) -> dict:
    email = settings.seed_admin_email
    password = settings.seed_admin_password
    phone = settings.seed_admin_phone
    demo_data = settings.seed_demo_data if demo_data is None else demo_data

    if not email:
        raise SystemExit("SEED_ADMIN_EMAIL is not set - nothing to create.")
    if not password:
        raise SystemExit(
            "SEED_ADMIN_PASSWORD is not set. Set it in the environment (never as a "
            "command-line argument) and run again."
        )

    async with AsyncSessionLocal() as db:
        admin_result = await _seed_admin(
            db, email=email, password=password, phone=phone, reset_password=reset_password
        )
        catalogue = await _seed_catalogue(db) if demo_data else {}
        await db.commit()

    return {"status": "ok", "admin_email": email, "admin": admin_result, **catalogue}


def main(argv: list[str] | None = None) -> int:
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Create the first admin user and starter data.")
    parser.add_argument("--no-demo-data", action="store_true",
                        help="Create only the admin account, no categories/products/cycles.")
    parser.add_argument("--reset-password", action="store_true",
                        help="If the admin already exists, reset its password to SEED_ADMIN_PASSWORD.")
    args = parser.parse_args(argv)

    configure_logging()
    result = asyncio.run(run(
        demo_data=False if args.no_demo_data else None,
        reset_password=args.reset_password,
    ))
    # Logs the outcome, never the credential.
    logger.info("seed_completed", **result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
