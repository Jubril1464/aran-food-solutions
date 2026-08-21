"""Supplier management is out of scope for this build phase (PRD FR-009/FR-010).

This router is intentionally a placeholder so the module boundary exists in the
codebase ahead of the Operations phase, without building any supplier tables yet.
"""

from fastapi import APIRouter, HTTPException, status

from app.core.deps import require_admin
from fastapi import Depends

router = APIRouter(prefix="/admin/suppliers", tags=["admin:suppliers (future phase)"], dependencies=[Depends(require_admin)])


@router.get("")
async def not_implemented():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Supplier management ships in the Operations phase, not this MVP pass.",
    )
