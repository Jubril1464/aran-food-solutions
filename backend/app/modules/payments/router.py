from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_customer
from app.core.rate_limit import limiter
from app.models.user import User
from app.modules.payments import service
from app.schemas.payment import InitializePaymentRequest, InitializePaymentResponse, PaymentResponse

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/initialize", response_model=InitializePaymentResponse)
@limiter.limit("10/minute")
async def initialize_payment(
    request: Request,
    data: InitializePaymentRequest,
    user: User = Depends(require_customer),
    db: AsyncSession = Depends(get_db),
):
    result = await service.initialize_payment(db, user, data.order_number)
    return InitializePaymentResponse(**result)


@router.post("/webhook/paystack", status_code=200)
@limiter.limit("60/minute")
async def paystack_webhook(
    request: Request,
    x_paystack_signature: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    body = await request.body()
    await service.handle_webhook(db, body, x_paystack_signature)
    return {"received": True}


@router.get("/{reference}/verify", response_model=PaymentResponse)
@limiter.limit("30/minute")
async def verify_payment(request: Request, reference: str, db: AsyncSession = Depends(get_db)):
    return await service.verify_and_apply(db, reference)
