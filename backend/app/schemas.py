from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


# ---- Auth
class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    venue_id: uuid.UUID
    user_id: uuid.UUID


# ---- Bootstrap (pre-carga del dispositivo)
class ProductOut(BaseModel):
    id: uuid.UUID
    sku: str
    name: str
    category: str
    sale_price: Decimal
    qty_on_hand: int


class TicketLite(BaseModel):
    id: uuid.UUID
    qr_code: str
    ticket_type_id: uuid.UUID
    status: str


class EventOut(BaseModel):
    id: uuid.UUID
    name: str
    starts_at: datetime
    ends_at: datetime
    capacity: int
    status: str


class BootstrapOut(BaseModel):
    venue_id: uuid.UUID
    event: EventOut | None
    products: list[ProductOut]
    tickets: list[TicketLite]
    server_time: datetime


# ---- Sync batch (outbox → servidor)
class SaleItemIn(BaseModel):
    product_id: uuid.UUID
    qty: int
    unit_price: Decimal
    discount: Decimal = Decimal("0")


class SaleOp(BaseModel):
    kind: Literal["sale"] = "sale"
    client_uuid: uuid.UUID
    event_id: uuid.UUID
    device_id: uuid.UUID
    total: Decimal
    payment_method: str = "cash"
    created_at: datetime
    items: list[SaleItemIn]


class AccessOp(BaseModel):
    kind: Literal["access"] = "access"
    client_uuid: uuid.UUID
    ticket_id: uuid.UUID
    event_id: uuid.UUID
    device_id: uuid.UUID
    direction: Literal["in", "out"] = "in"
    scanned_at: datetime


class StockOp(BaseModel):
    kind: Literal["stock"] = "stock"
    client_uuid: uuid.UUID
    product_id: uuid.UUID
    event_id: uuid.UUID | None = None
    type: Literal["in", "out", "adjust", "waste"]
    qty_delta: int
    reason: str | None = None


SyncOp = SaleOp | AccessOp | StockOp


class SyncBatchIn(BaseModel):
    device_id: uuid.UUID
    ops: list[SyncOp] = Field(default_factory=list)


class OpResult(BaseModel):
    client_uuid: uuid.UUID
    status: Literal["accepted", "duplicate", "conflict", "error"]
    reason: str | None = None
    server_id: uuid.UUID | None = None


class SyncBatchOut(BaseModel):
    results: list[OpResult]
    server_time: datetime
