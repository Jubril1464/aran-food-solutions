"""Inventory & quality control is out of scope for this build phase (PRD FR-012/FR-013).

Placeholder router only — no inventory/product_batch tables are created yet.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import require_admin

router = APIRouter(prefix="/admin/inventory", tags=["admin:inventory (future phase)"], dependencies=[Depends(require_admin)])


@router.get("")
async def not_implemented():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Inventory management ships in the Operations phase, not this MVP pass.",
    )
