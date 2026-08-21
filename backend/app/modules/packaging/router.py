"""Packaging & fulfillment is out of scope for this build phase (PRD FR-014).

Placeholder router only — no packaging_records table is created yet.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import require_admin

router = APIRouter(prefix="/admin/packaging", tags=["admin:packaging (future phase)"], dependencies=[Depends(require_admin)])


@router.get("")
async def not_implemented():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Packaging management ships in the Operations phase, not this MVP pass.",
    )
