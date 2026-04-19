"""Cuentas pre-pagadas (cashless) con QR/NFC. Operaciones online + offline via sync."""
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
from ..models import Tab, TabMovement, User

router = APIRouter(prefix="/tabs", tags=["tabs"])


class TabCreateIn(BaseModel):
    code: str
    holder_name: str | None = None
    holder_doc: str | None = None
    initial_load: Decimal = Decimal("0")
    event_id: uuid.UUID | None = None


class TabOut(BaseModel):
    id: uuid.UUID
    code: str
    holder_name: str | None
    balance: Decimal
    status: str
    opened_at: datetime
    closed_at: datetime | None


@router.post("", response_model=TabOut, status_code=status.HTTP_201_CREATED)
def create_tab(
    body: TabCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.execute(
        select(Tab).where(Tab.venue_id == user.venue_id, Tab.code == body.code)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "código ya existe")

    tab = Tab(
        venue_id=user.venue_id,
        event_id=body.event_id,
        code=body.code,
        holder_name=body.holder_name,
        holder_doc=body.holder_doc,
        balance=body.initial_load,
    )
    db.add(tab)
    db.flush()

    if body.initial_load and body.initial_load > 0:
        db.add(
            TabMovement(
                client_uuid=uuid.uuid4(),
                tab_id=tab.id,
                kind="load",
                amount=body.initial_load,
                user_id=user.id,
            )
        )
    db.commit()
    db.refresh(tab)
    return _out(tab)


@router.get("/by-code/{code}", response_model=TabOut)
def get_by_code(
    code: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tab = db.execute(
        select(Tab).where(Tab.venue_id == user.venue_id, Tab.code == code)
    ).scalar_one_or_none()
    if not tab:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "cuenta no encontrada")
    return _out(tab)


class TabLoadIn(BaseModel):
    amount: Decimal
    client_uuid: uuid.UUID | None = None


@router.post("/{tab_id}/load", response_model=TabOut)
def load_tab(
    tab_id: uuid.UUID,
    body: TabLoadIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.amount <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "monto inválido")
    tab = db.get(Tab, tab_id)
    if not tab or tab.venue_id != user.venue_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "cuenta no encontrada")
    if tab.status != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "cuenta no activa")

    cuuid = body.client_uuid or uuid.uuid4()
    dup = db.execute(select(TabMovement).where(TabMovement.client_uuid == cuuid)).scalar_one_or_none()
    if dup:
        return _out(tab)

    db.add(TabMovement(client_uuid=cuuid, tab_id=tab.id, kind="load", amount=body.amount, user_id=user.id))
    tab.balance = (tab.balance or Decimal(0)) + body.amount
    db.commit()
    db.refresh(tab)
    return _out(tab)


@router.post("/{tab_id}/close", response_model=TabOut)
def close_tab(
    tab_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cierra la cuenta. Si hay saldo remanente se registra como refund."""
    tab = db.get(Tab, tab_id)
    if not tab or tab.venue_id != user.venue_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "cuenta no encontrada")
    if tab.status == "closed":
        return _out(tab)

    remainder = tab.balance or Decimal(0)
    if remainder > 0:
        db.add(
            TabMovement(
                client_uuid=uuid.uuid4(),
                tab_id=tab.id,
                kind="refund",
                amount=-remainder,
                user_id=user.id,
            )
        )
        tab.balance = Decimal(0)
    tab.status = "closed"
    tab.closed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(tab)
    return _out(tab)


@router.get("", response_model=list[TabOut])
def list_tabs(
    status_filter: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = select(Tab).where(Tab.venue_id == user.venue_id)
    if status_filter:
        q = q.where(Tab.status == status_filter)
    rows = db.execute(q.order_by(Tab.opened_at.desc()).limit(200)).scalars().all()
    return [_out(t) for t in rows]


def _out(t: Tab) -> TabOut:
    bal = (t.balance if t.balance is not None else Decimal(0)).quantize(Decimal("0.01"))
    return TabOut(
        id=t.id,
        code=t.code,
        holder_name=t.holder_name,
        balance=bal,
        status=t.status,
        opened_at=t.opened_at,
        closed_at=t.closed_at,
    )
