"""Turnos de caja con arqueo al cierre."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user
from ..models import Sale, Shift, User

router = APIRouter(prefix="/shifts", tags=["shifts"])


class ShiftOpenIn(BaseModel):
    device_id: uuid.UUID
    event_id: uuid.UUID | None = None
    opening_cash: Decimal = Decimal("0")


class ShiftCloseIn(BaseModel):
    closing_cash: Decimal
    notes: str | None = None


class ShiftOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    device_id: uuid.UUID
    event_id: uuid.UUID | None
    opened_at: datetime
    closed_at: datetime | None
    opening_cash: Decimal
    closing_cash: Decimal | None
    expected_cash: Decimal | None
    cash_variance: Decimal | None
    notes: str | None


@router.post("/open", response_model=ShiftOut)
def open_shift(
    body: ShiftOpenIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current = db.execute(
        select(Shift).where(
            Shift.user_id == user.id,
            Shift.device_id == body.device_id,
            Shift.closed_at.is_(None),
        )
    ).scalar_one_or_none()
    if current:
        raise HTTPException(status.HTTP_409_CONFLICT, "ya hay un turno abierto en este dispositivo")

    s = Shift(
        venue_id=user.venue_id,
        user_id=user.id,
        device_id=body.device_id,
        event_id=body.event_id,
        opening_cash=body.opening_cash,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _out(s)


@router.get("/current", response_model=ShiftOut | None)
def current_shift(
    device_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    s = db.execute(
        select(Shift).where(
            Shift.user_id == user.id,
            Shift.device_id == device_id,
            Shift.closed_at.is_(None),
        )
    ).scalar_one_or_none()
    return _out(s) if s else None


@router.post("/{shift_id}/close", response_model=ShiftOut)
def close_shift(
    shift_id: uuid.UUID,
    body: ShiftCloseIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    s = db.get(Shift, shift_id)
    if not s or s.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "turno no encontrado")
    if s.closed_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "turno ya cerrado")

    # Efectivo esperado = apertura + suma de ventas en efectivo del turno.
    cash_sales = db.execute(
        select(func.coalesce(func.sum(Sale.total), 0))
        .where(Sale.shift_id == shift_id, Sale.payment_method == "cash")
    ).scalar_one()

    expected = (s.opening_cash or Decimal("0")) + Decimal(cash_sales or 0)
    s.closing_cash = body.closing_cash
    s.expected_cash = expected
    s.cash_variance = Decimal(body.closing_cash) - expected
    s.closed_at = datetime.now(timezone.utc)
    s.notes = body.notes
    db.commit()
    db.refresh(s)
    return _out(s)


@router.get("", response_model=list[ShiftOut])
def list_shifts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Shift).where(Shift.venue_id == user.venue_id).order_by(Shift.opened_at.desc()).limit(50)
    ).scalars().all()
    return [_out(s) for s in rows]


def _out(s: Shift) -> ShiftOut:
    return ShiftOut(
        id=s.id,
        user_id=s.user_id,
        device_id=s.device_id,
        event_id=s.event_id,
        opened_at=s.opened_at,
        closed_at=s.closed_at,
        opening_cash=s.opening_cash or Decimal(0),
        closing_cash=s.closing_cash,
        expected_cash=s.expected_cash,
        cash_variance=s.cash_variance,
        notes=s.notes,
    )
