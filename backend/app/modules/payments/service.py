from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import NotificationType
from app.models.order import OrderStatus
from app.models.payment import Payment, PaymentStatus
from app.models.user import User
from app.modules.notifications.service import notify
from app.modules.orders.service import get_order_by_id, get_order_by_number, transition_order
from app.modules.payments.paystack import PaystackClient, generate_reference


async def initialize_payment(db: AsyncSession, user: User, order_number: str) -> dict:
    order = await get_order_by_number(db, order_number, owner=user)
    if order.status != OrderStatus.PENDING_PAYMENT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order is not awaiting payment")

    reference = generate_reference()
    client = PaystackClient()
    result = await client.initialize_transaction(
        email=user.email, amount=Decimal(order.total), reference=reference, metadata={"order_id": str(order.id)}
    )

    payment = Payment(
        order_id=order.id,
        provider="paystack",
        reference=result["reference"],
        amount=order.total,
        status=PaymentStatus.PENDING,
    )
    db.add(payment)
    await db.commit()
    return result


async def _get_payment_for_update(db: AsyncSession, reference: str) -> Payment | None:
    return (
        await db.execute(select(Payment).where(Payment.reference == reference).with_for_update())
    ).scalar_one_or_none()


async def verify_and_apply(db: AsyncSession, reference: str) -> Payment:
    """Idempotent: verifies against Paystack and applies the result exactly once.
    A second call (retry, replayed webhook, manual verify after webhook already
    landed) is a no-op once the payment is in a terminal state."""
    payment = await _get_payment_for_update(db, reference)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    if payment.status in (PaymentStatus.SUCCESSFUL, PaymentStatus.FAILED):
        return payment  # already processed — idempotent no-op

    client = PaystackClient()
    result = await client.verify_transaction(reference)

    order = await get_order_by_id(db, payment.order_id)
    user = (await db.execute(select(User).where(User.id == order.user_id))).scalar_one()

    if result["status"] == "success":
        payment.status = PaymentStatus.SUCCESSFUL
        payment.method = result.get("channel")
        payment.verified_at = datetime.now(timezone.utc)
        payment.raw_payload = {k: str(v) for k, v in result.items()}

        if order.status == OrderStatus.PENDING_PAYMENT:
            await transition_order(db, order, OrderStatus.PAID, note="Payment verified")
            await transition_order(db, order, OrderStatus.CONFIRMED, note="Order confirmed after payment")
            await notify(
                db, user=user, notification_type=NotificationType.PAYMENT_CONFIRMED,
                payload={"order_number": order.order_number, "amount": str(payment.amount)},
            )
            await notify(
                db, user=user, notification_type=NotificationType.ORDER_CONFIRMED,
                payload={"order_number": order.order_number, "cycle_name": order.items[0].procurement_cycle.name if order.items else "N/A"},
            )
    else:
        payment.status = PaymentStatus.FAILED
        payment.raw_payload = {k: str(v) for k, v in result.items()}
        await notify(
            db, user=user, notification_type=NotificationType.PAYMENT_FAILED,
            payload={"order_number": order.order_number},
        )

    await db.commit()
    await db.refresh(payment)
    return payment


async def handle_webhook(db: AsyncSession, body: bytes, signature: str | None) -> None:
    client = PaystackClient()
    if not client.verify_webhook_signature(body, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")

    import json

    payload = json.loads(body)
    reference = payload.get("data", {}).get("reference")
    if not reference:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing transaction reference")

    await verify_and_apply(db, reference)
