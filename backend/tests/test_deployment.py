"""Tests for the pieces the hosted deployment depends on.

Two of them are new and load-bearing:

  * `normalize_database_url` - what makes a connection string copied straight
    from a managed Postgres dashboard work, instead of crashing asyncpg on the
    first query.
  * the in-process notification queue - the reason this app needs no Redis and
    no second service, and therefore fits on one free instance.

The rest of the suite mocks the notification queue out entirely (see
conftest.py), so without these tests the actual delivery path would never run.
"""

import asyncio
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.core.database import AsyncSessionLocal, normalize_database_url
from app.core.queue import InProcessNotificationQueue, redeliver_pending
from app.models.notification import Notification, NotificationStatus, NotificationType
from app.models.user import User


# --------------------------------------------------------------- URL handling --


def test_neon_style_url_is_made_asyncpg_safe():
    """The exact shape Neon hands you, which asyncpg rejects verbatim.

    asyncpg has no `sslmode`/`channel_binding` keyword arguments, so leaving them
    in the URL raises TypeError on the first connection - after a successful
    deploy, which makes it a particularly annoying way to fail.
    """
    url, ssl_requested = normalize_database_url(
        "postgresql://user:pw@ep-cool-name-123456.eu-central-1.aws.neon.tech/agric"
        "?sslmode=require&channel_binding=require"
    )
    assert url == "postgresql+asyncpg://user:pw@ep-cool-name-123456.eu-central-1.aws.neon.tech/agric"
    assert ssl_requested is True


def test_legacy_postgres_scheme_is_upgraded():
    url, _ = normalize_database_url("postgres://user:pw@host:5432/db")
    assert url == "postgresql+asyncpg://user:pw@host:5432/db"


def test_unrelated_query_parameters_are_preserved():
    url, ssl_requested = normalize_database_url(
        "postgresql://u:p@host/db?sslmode=require&application_name=agric"
    )
    assert url == "postgresql+asyncpg://u:p@host/db?application_name=agric"
    assert ssl_requested is True


def test_sqlite_and_already_async_urls_are_left_alone():
    assert normalize_database_url("sqlite+aiosqlite:///./dev.db") == ("sqlite+aiosqlite:///./dev.db", False)
    assert normalize_database_url("postgresql+asyncpg://u:p@host/db") == ("postgresql+asyncpg://u:p@host/db", False)


def test_ssl_is_not_requested_when_the_url_disables_it():
    url, ssl_requested = normalize_database_url("postgresql://u:p@host/db?sslmode=disable")
    assert url == "postgresql+asyncpg://u:p@host/db"
    assert ssl_requested is False


# ------------------------------------------------------------- seeded admin --


@pytest.mark.asyncio
async def test_seeded_admin_can_actually_log_in(client, monkeypatch):
    """Regression: the seeded admin address must survive request validation.

    The seed writes the user straight through the model, bypassing pydantic - so
    an address like `admin@agric.local` seeds happily and is then rejected by
    LoginRequest's EmailStr (`.local` is an RFC 6761 special-use name). The result
    is an admin account that exists and can never log in, with a 422 that says
    nothing about the real cause. Nothing else in the suite would catch it.
    """
    from app import seed
    from app.core.config import get_settings

    settings = get_settings()
    password = "seeded-admin-password-123"
    monkeypatch.setattr(settings, "seed_admin_password", password)
    monkeypatch.setattr(settings, "seed_demo_data", False)

    result = await seed.run()
    assert result["admin"] == "created", result

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": settings.seed_admin_email, "password": password},
    )
    assert response.status_code == 200, (
        f"the seeded admin cannot log in: {response.status_code} {response.text}"
    )
    assert response.json()["access_token"]


# ------------------------------------------------------- in-process delivery --


@pytest_asyncio.fixture
async def real_in_process_queue(monkeypatch):
    """Undo conftest's autouse queue mock for this module.

    Applied after the autouse fixture, so this wins.
    """
    monkeypatch.setattr(
        "app.modules.notifications.service.get_notification_queue",
        lambda: InProcessNotificationQueue(),
    )
    monkeypatch.setattr("app.core.queue.get_notification_queue", lambda: InProcessNotificationQueue())


async def _wait_for_status(notification_id: uuid.UUID, status: NotificationStatus, timeout: float = 15.0):
    """Poll until the background task has done its work, or give up."""
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        async with AsyncSessionLocal() as db:
            row = (
                await db.execute(select(Notification).where(Notification.id == notification_id))
            ).scalar_one_or_none()
            if row is not None and row.status == status:
                return row
        await asyncio.sleep(0.1)
    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(select(Notification).where(Notification.id == notification_id))
        ).scalar_one_or_none()
    pytest.fail(f"notification never reached {status}; last state: {row and row.status}")


@pytest.mark.asyncio
async def test_registration_notification_is_delivered_in_the_background(client, real_in_process_queue):
    """The whole point: a request enqueues, returns immediately, and delivery
    still happens - including surviving the fact that the notification row isn't
    committed yet when the background task first looks for it."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Background Delivery",
            "email": "background@agric-mvp-test.com",
            "phone_number": "+2348090000001",
            "password": "supersecret123",
            "street": "1 Test Road",
            "city": "Ibadan",
            "state": "Oyo",
        },
    )
    assert response.status_code == 201, response.text

    async with AsyncSessionLocal() as db:
        notification = (await db.execute(select(Notification))).scalars().one()
    assert notification.type == NotificationType.ACCOUNT_VERIFICATION

    delivered = await _wait_for_status(notification.id, NotificationStatus.SENT)
    assert delivered.sent_at is not None


@pytest.mark.asyncio
async def test_pending_notifications_are_redelivered_on_startup(real_in_process_queue):
    """A task enqueued in-process dies with the process. This is the sweep that
    stops a deploy (or a free instance spinning down) from losing it."""
    async with AsyncSessionLocal() as db:
        user = User(
            full_name="Sweep Target",
            phone_number="+2348090000002",
            email="sweep@agric-mvp-test.com",
            password_hash="x",
            is_verified=True,
        )
        db.add(user)
        await db.flush()
        # A notification left behind by a process that exited before delivering.
        orphan = Notification(
            user_id=user.id,
            type=NotificationType.ORDER_CONFIRMED,
            channel="email",
            payload={"full_name": user.full_name, "order_number": "ORD-1", "cycle_name": "Cycle 1"},
        )
        db.add(orphan)
        await db.commit()
        orphan_id = orphan.id

    assert await redeliver_pending() == 1
    await _wait_for_status(orphan_id, NotificationStatus.SENT)


@pytest.mark.asyncio
async def test_already_sent_notifications_are_not_redelivered(real_in_process_queue):
    """The sweep must not re-send everything it finds - only PENDING rows."""
    async with AsyncSessionLocal() as db:
        user = User(
            full_name="Done Already",
            phone_number="+2348090000003",
            email="done@agric-mvp-test.com",
            password_hash="x",
            is_verified=True,
        )
        db.add(user)
        await db.flush()
        db.add(
            Notification(
                user_id=user.id,
                type=NotificationType.ORDER_CONFIRMED,
                channel="email",
                payload={"full_name": user.full_name, "order_number": "ORD-2", "cycle_name": "Cycle 1"},
                status=NotificationStatus.SENT,
            )
        )
        await db.commit()

    assert await redeliver_pending() == 0
