import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User
from app.modules.procurement import service
from app.schemas.procurement import (
    AggregationLine,
    AggregationReport,
    ProcurementCycleCreate,
    ProcurementCycleResponse,
    ProcurementCycleUpdate,
)

router = APIRouter(prefix="/admin/procurement-cycles", tags=["admin:procurement"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[ProcurementCycleResponse])
async def list_cycles(db: AsyncSession = Depends(get_db)):
    return await service.list_cycles(db)


@router.post("", response_model=ProcurementCycleResponse, status_code=201)
async def create_cycle(data: ProcurementCycleCreate, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await service.create_cycle(db, admin, data)


@router.get("/{cycle_id}", response_model=ProcurementCycleResponse)
async def get_cycle(cycle_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await service.get_cycle(db, cycle_id)


@router.put("/{cycle_id}", response_model=ProcurementCycleResponse)
async def update_cycle(
    cycle_id: uuid.UUID,
    data: ProcurementCycleUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.update_cycle(db, admin, cycle_id, data)


@router.post("/{cycle_id}/open", response_model=ProcurementCycleResponse)
async def open_cycle(cycle_id: uuid.UUID, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await service.open_cycle(db, admin, cycle_id)


@router.post("/{cycle_id}/close", response_model=ProcurementCycleResponse)
async def close_cycle(cycle_id: uuid.UUID, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await service.close_cycle(db, admin, cycle_id)


@router.get("/{cycle_id}/aggregation", response_model=AggregationReport)
async def get_aggregation(cycle_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    cycle, lines = await service.get_aggregation_report(db, cycle_id)
    return AggregationReport(
        cycle_id=cycle.id,
        cycle_name=cycle.name,
        lines=[
            AggregationLine(product_id=p.id, product_name=p.name, unit=p.unit, total_quantity=qty)
            for p, qty in lines
        ],
    )
