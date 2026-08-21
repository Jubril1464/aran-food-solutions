import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.procurement import CycleStatus


class ProcurementCycleCreate(BaseModel):
    name: str
    category_id: uuid.UUID | None = None
    order_window_opens_at: datetime
    order_window_closes_at: datetime


class ProcurementCycleUpdate(BaseModel):
    name: str | None = None
    order_window_opens_at: datetime | None = None
    order_window_closes_at: datetime | None = None


class ProcurementCycleResponse(BaseModel):
    id: uuid.UUID
    name: str
    category_id: uuid.UUID | None
    order_window_opens_at: datetime
    order_window_closes_at: datetime
    status: CycleStatus

    model_config = {"from_attributes": True}


class AggregationLine(BaseModel):
    product_id: uuid.UUID
    product_name: str
    unit: str
    total_quantity: Decimal


class AggregationReport(BaseModel):
    cycle_id: uuid.UUID
    cycle_name: str
    lines: list[AggregationLine]
