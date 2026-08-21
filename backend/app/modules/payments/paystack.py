import uuid
from decimal import Decimal
from typing import Any

import httpx

from app.core.config import get_settings

settings = get_settings()


class PaystackClient:
    """Thin wrapper around the Paystack Transactions API.

    When PAYSTACK_SECRET_KEY is not configured (local dev without a Paystack
    account), falls back to an in-process mock so the checkout flow can still
    be exercised end-to-end; real deployments must set the env var.
    """

    def __init__(self) -> None:
        self.secret_key = settings.paystack_secret_key
        self.base_url = settings.paystack_base_url

    @property
    def mock_mode(self) -> bool:
        return not self.secret_key

    async def initialize_transaction(self, *, email: str, amount: Decimal, reference: str, metadata: dict) -> dict[str, Any]:
        if self.mock_mode:
            return {
                "authorization_url": f"{settings.frontend_url}/mock-paystack-checkout?reference={reference}",
                "access_code": f"mock_{reference}",
                "reference": reference,
            }
        async with httpx.AsyncClient(base_url=self.base_url, timeout=15) as client:
            response = await client.post(
                "/transaction/initialize",
                headers={"Authorization": f"Bearer {self.secret_key}"},
                json={
                    "email": email,
                    "amount": int(amount * 100),  # kobo
                    "reference": reference,
                    "metadata": metadata,
                },
            )
            response.raise_for_status()
            data = response.json()["data"]
            return {
                "authorization_url": data["authorization_url"],
                "access_code": data["access_code"],
                "reference": data["reference"],
            }

    async def verify_transaction(self, reference: str) -> dict[str, Any]:
        if self.mock_mode:
            return {"status": "success", "amount": None, "channel": "mock", "reference": reference}
        async with httpx.AsyncClient(base_url=self.base_url, timeout=15) as client:
            response = await client.get(
                f"/transaction/verify/{reference}",
                headers={"Authorization": f"Bearer {self.secret_key}"},
            )
            response.raise_for_status()
            data = response.json()["data"]
            return {
                "status": data["status"],
                "amount": Decimal(data["amount"]) / 100,
                "channel": data.get("channel"),
                "reference": data["reference"],
            }

    def verify_webhook_signature(self, body: bytes, signature: str | None) -> bool:
        if self.mock_mode:
            return True
        if not signature:
            return False
        import hashlib
        import hmac

        expected = hmac.new(self.secret_key.encode(), body, hashlib.sha512).hexdigest()
        return hmac.compare_digest(expected, signature)


def generate_reference() -> str:
    return f"agric_{uuid.uuid4().hex}"
