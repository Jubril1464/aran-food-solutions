"""Delivery management is out of scope for this build phase (PRD FR-015).

Placeholder router only — no deliveries table is created yet.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import require_admin

router = APIRouter(prefix="/admin/delivery", tags=["admin:delivery (future phase)"], dependencies=[Depends(require_admin)])


@router.get("")
async def not_implemented():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Delivery management ships in the Operations phase, not this MVP pass.",
    )
