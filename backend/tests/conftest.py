import os
import uuid

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_agric.db"
os.environ["JWT_SECRET"] = "test-secret-key-for-pytest-only-not-for-prod-use"
os.environ["PAYSTACK_SECRET_KEY"] = ""  # forces PaystackClient mock mode

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.database import AsyncSessionLocal, Base, engine
from app.core.security import hash_password
from app.models.user import User, UserRole


class FakeNotificationQueue:
    async def enqueue(self, notification_id: str) -> None:
        return None


@pytest_asyncio.fixture(autouse=True)
async def _fake_notifications(monkeypatch):
    monkeypatch.setattr(
        "app.modules.notifications.service.get_notification_queue", lambda: FakeNotificationQueue()
    )


@pytest_asyncio.fixture(autouse=True)
async def _reset_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def admin_user():
    async with AsyncSessionLocal() as db:
        user = User(
            full_name="Admin User",
            phone_number=f"+234{uuid.uuid4().int % 10**10:010d}",
            email="admin@agric-mvp-test.com",
            password_hash=hash_password("adminpass123"),
            role=UserRole.ADMIN,
            is_verified=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


@pytest_asyncio.fixture
async def admin_token(client, admin_user):
    resp = await client.post("/api/v1/auth/login", json={"email": "admin@agric-mvp-test.com", "password": "adminpass123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]
