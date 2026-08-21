from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import create_email_verify_token, create_password_reset_token
from app.models.user import User

API = "/api/v1"


async def _get_user_id(email: str) -> str:
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        return str(user.id)


async def _register_and_verify(client, email="customer@agric-mvp-test.com", password="customerpass123"):
    resp = await client.post(
        f"{API}/auth/register",
        json={
            "full_name": "Jane Doe",
            "phone_number": "+2348011112222",
            "email": email,
            "password": password,
            "street": "12 Market Road",
            "city": "Lagos",
            "state": "Lagos",
        },
    )
    assert resp.status_code == 201, resp.text
    user_id = await _get_user_id(email)
    token = create_email_verify_token(user_id)
    verify_resp = await client.post(f"{API}/auth/verify", json={"token": token})
    assert verify_resp.status_code == 200, verify_resp.text
    login_resp = await client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200, login_resp.text
    return login_resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _setup_category_and_product(client, admin_token, moq=5):
    cat_resp = await client.post(f"{API}/admin/categories", json={"name": "Grains"}, headers=_auth(admin_token))
    assert cat_resp.status_code == 201, cat_resp.text
    category = cat_resp.json()

    product_resp = await client.post(
        f"{API}/admin/products",
        json={
            "name": "Rice",
            "category_id": category["id"],
            "unit": "kg",
            "price": "1000.00",
            "minimum_order_quantity": str(moq),
        },
        headers=_auth(admin_token),
    )
    assert product_resp.status_code == 201, product_resp.text
    return category, product_resp.json()


async def _create_open_cycle(client, admin_token, category_id):
    now = datetime.now(timezone.utc)
    create_resp = await client.post(
        f"{API}/admin/procurement-cycles",
        json={
            "name": "Week 34 cycle",
            "category_id": category_id,
            "order_window_opens_at": (now - timedelta(hours=1)).isoformat(),
            "order_window_closes_at": (now + timedelta(hours=1)).isoformat(),
        },
        headers=_auth(admin_token),
    )
    assert create_resp.status_code == 201, create_resp.text
    cycle = create_resp.json()
    open_resp = await client.post(f"{API}/admin/procurement-cycles/{cycle['id']}/open", headers=_auth(admin_token))
    assert open_resp.status_code == 200, open_resp.text
    return open_resp.json()


async def test_register_login_reset_round_trip(client):
    token = await _register_and_verify(client)
    me = await client.get(f"{API}/auth/me", headers=_auth(token))
    assert me.status_code == 200
    assert me.json()["is_verified"] is True

    reset_req = await client.post(f"{API}/auth/password-reset/request", json={"email": "customer@agric-mvp-test.com"})
    assert reset_req.status_code == 204

    user_id = await _get_user_id("customer@agric-mvp-test.com")
    reset_token = create_password_reset_token(user_id)
    confirm = await client.post(
        f"{API}/auth/password-reset/confirm", json={"token": reset_token, "new_password": "newpassword456"}
    )
    assert confirm.status_code == 204

    old_login = await client.post(f"{API}/auth/login", json={"email": "customer@agric-mvp-test.com", "password": "customerpass123"})
    assert old_login.status_code == 401

    new_login = await client.post(f"{API}/auth/login", json={"email": "customer@agric-mvp-test.com", "password": "newpassword456"})
    assert new_login.status_code == 200


async def test_moq_enforcement(client, admin_token):
    customer_token = await _register_and_verify(client)
    _, product = await _setup_category_and_product(client, admin_token, moq=5)

    under_moq = await client.post(
        f"{API}/cart/items", json={"product_id": product["id"], "quantity": "2"}, headers=_auth(customer_token)
    )
    assert under_moq.status_code == 400
    assert "Minimum order quantity" in under_moq.json()["detail"]

    ok = await client.post(
        f"{API}/cart/items", json={"product_id": product["id"], "quantity": "10"}, headers=_auth(customer_token)
    )
    assert ok.status_code == 200
    assert ok.json()["subtotal"] == "10000.00"


async def test_checkout_rejects_when_no_active_cycle(client, admin_token):
    customer_token = await _register_and_verify(client)
    _, product = await _setup_category_and_product(client, admin_token, moq=1)
    # No procurement cycle created/opened for this category.

    await client.post(f"{API}/cart/items", json={"product_id": product["id"], "quantity": "1"}, headers=_auth(customer_token))
    addr = await client.post(
        f"{API}/users/addresses",
        json={"street": "1 Test St", "city": "Lagos", "state": "Lagos", "phone_number": "+2348011112222"},
        headers=_auth(customer_token),
    )
    assert addr.status_code == 201
    checkout = await client.post(
        f"{API}/orders/checkout",
        json={"delivery_address_id": addr.json()["id"]},
        headers=_auth(customer_token),
    )
    assert checkout.status_code == 400
    assert "procurement cycle" in checkout.json()["detail"]


async def test_full_checkout_payment_and_cycle_close_flow(client, admin_token):
    customer_token = await _register_and_verify(client)
    category, product = await _setup_category_and_product(client, admin_token, moq=5)
    cycle = await _create_open_cycle(client, admin_token, category["id"])

    await client.post(
        f"{API}/cart/items", json={"product_id": product["id"], "quantity": "10"}, headers=_auth(customer_token)
    )
    addr = await client.post(
        f"{API}/users/addresses",
        json={"street": "1 Test St", "city": "Lagos", "state": "Lagos", "phone_number": "+2348011112222"},
        headers=_auth(customer_token),
    )
    checkout = await client.post(
        f"{API}/orders/checkout",
        json={"delivery_address_id": addr.json()["id"]},
        headers=_auth(customer_token),
    )
    assert checkout.status_code == 201, checkout.text
    order = checkout.json()
    assert order["status"] == "PENDING_PAYMENT"
    assert order["items"][0]["procurement_cycle_id"] == cycle["id"]
    order_number = order["order_number"]

    init = await client.post(
        f"{API}/payments/initialize", json={"order_number": order_number}, headers=_auth(customer_token)
    )
    assert init.status_code == 200, init.text
    reference = init.json()["reference"]

    verify1 = await client.get(f"{API}/payments/{reference}/verify")
    assert verify1.status_code == 200
    assert verify1.json()["status"] == "successful"

    tracked = await client.get(f"{API}/orders/{order_number}", headers=_auth(customer_token))
    assert tracked.status_code == 200
    assert tracked.json()["status"] == "CONFIRMED"
    statuses = [h["status"] for h in tracked.json()["status_history"]]
    assert statuses == ["PENDING_PAYMENT", "PAID", "CONFIRMED"]

    # Idempotency: replaying verify (simulating a duplicate webhook delivery) must not re-apply.
    verify2 = await client.get(f"{API}/payments/{reference}/verify")
    assert verify2.status_code == 200
    tracked_again = await client.get(f"{API}/orders/{order_number}", headers=_auth(customer_token))
    assert tracked_again.json()["status"] == "CONFIRMED"
    assert len(tracked_again.json()["status_history"]) == 3  # unchanged, not duplicated

    history = await client.get(f"{API}/orders", headers=_auth(customer_token))
    assert history.status_code == 200
    assert history.json()["total"] == 1

    aggregation = await client.get(
        f"{API}/admin/procurement-cycles/{cycle['id']}/aggregation", headers=_auth(admin_token)
    )
    assert aggregation.status_code == 200
    lines = aggregation.json()["lines"]
    assert len(lines) == 1
    assert lines[0]["total_quantity"] == "10.00"

    close = await client.post(f"{API}/admin/procurement-cycles/{cycle['id']}/close", headers=_auth(admin_token))
    assert close.status_code == 200
    assert close.json()["status"] == "closed"

    tracked_final = await client.get(f"{API}/orders/{order_number}", headers=_auth(customer_token))
    assert tracked_final.json()["status"] == "PROCUREMENT"
    final_statuses = [h["status"] for h in tracked_final.json()["status_history"]]
    assert final_statuses == ["PENDING_PAYMENT", "PAID", "CONFIRMED", "AGGREGATING", "PROCUREMENT"]

    # An order mid-procurement can still be cancelled (e.g. supplier failure)...
    cancel = await client.post(f"{API}/admin/orders/{order_number}/cancel", headers=_auth(admin_token))
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "CANCELLED"

    # ...but CANCELLED is terminal: a second cancel on the same order is an invalid transition.
    invalid_cancel = await client.post(f"{API}/admin/orders/{order_number}/cancel", headers=_auth(admin_token))
    assert invalid_cancel.status_code == 409


async def test_only_one_open_cycle_per_category(client, admin_token):
    category, _ = await _setup_category_and_product(client, admin_token, moq=1)
    await _create_open_cycle(client, admin_token, category["id"])

    now = datetime.now(timezone.utc)
    second = await client.post(
        f"{API}/admin/procurement-cycles",
        json={
            "name": "Conflicting cycle",
            "category_id": category["id"],
            "order_window_opens_at": now.isoformat(),
            "order_window_closes_at": (now + timedelta(hours=2)).isoformat(),
        },
        headers=_auth(admin_token),
    )
    assert second.status_code == 201
    open_second = await client.post(
        f"{API}/admin/procurement-cycles/{second.json()['id']}/open", headers=_auth(admin_token)
    )
    assert open_second.status_code == 409
