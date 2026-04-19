"""RRPP con atribución de ventas y cálculo automático de comisiones."""
from __future__ import annotations

import re
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user, require_roles
from ..models import Event, Promoter, Ticket, TicketType, User

router = APIRouter(prefix="/promoters", tags=["promoters"])


def _slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")[:60] or "rrpp"


class PromoterIn(BaseModel):
    name: str
    phone: str | None = None
    commission_pct: Decimal = Decimal("10")
    slug: str | None = None


class PromoterOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    phone: str | None
    commission_pct: Decimal
    active: bool
    tickets_sold: int = 0
    revenue: Decimal = Decimal("0")
    commission_amount: Decimal = Decimal("0")


@router.post("", response_model=PromoterOut, status_code=status.HTTP_201_CREATED)
def create(body: PromoterIn, user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    slug = body.slug or _slugify(body.name)
    existing = db.execute(
        select(Promoter).where(Promoter.venue_id == user.venue_id, Promoter.slug == slug)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "slug duplicado")

    p = Promoter(
        venue_id=user.venue_id,
        name=body.name,
        slug=slug,
        phone=body.phone,
        commission_pct=body.commission_pct,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _out(db, p)


@router.get("", response_model=list[PromoterOut])
def list_all(user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Promoter).where(Promoter.venue_id == user.venue_id)
    ).scalars().all()
    return [_out(db, p) for p in rows]


@router.put("/{promoter_id}", response_model=PromoterOut)
def update(
    promoter_id: uuid.UUID,
    body: PromoterIn,
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    p = db.get(Promoter, promoter_id)
    if not p or p.venue_id != user.venue_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no encontrado")
    p.name = body.name
    if body.slug:
        p.slug = body.slug
    p.phone = body.phone
    p.commission_pct = body.commission_pct
    db.commit()
    db.refresh(p)
    return _out(db, p)


@router.post("/{promoter_id}/toggle", response_model=PromoterOut)
def toggle(
    promoter_id: uuid.UUID,
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    p = db.get(Promoter, promoter_id)
    if not p or p.venue_id != user.venue_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no encontrado")
    p.active = not p.active
    db.commit()
    db.refresh(p)
    return _out(db, p)


class AttributeTicketIn(BaseModel):
    ticket_id: uuid.UUID


@router.post("/{promoter_id}/attribute-ticket")
def attribute_ticket(
    promoter_id: uuid.UUID,
    body: AttributeTicketIn,
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Atribuye un ticket vendido al RRPP. Dispara la comisión automáticamente al calcular /analytics/commissions."""
    p = db.get(Promoter, promoter_id)
    if not p or p.venue_id != user.venue_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "promotor no encontrado")
    t = db.get(Ticket, body.ticket_id)
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ticket no encontrado")
    t.promoter_id = promoter_id
    db.commit()
    return {"ok": True}


def _out(db: Session, p: Promoter) -> PromoterOut:
    # Métricas agregadas: tickets vendidos + facturación + comisión estimada.
    agg = db.execute(
        select(func.count(Ticket.id), func.coalesce(func.sum(TicketType.price), 0))
        .select_from(Ticket)
        .join(TicketType, TicketType.id == Ticket.ticket_type_id)
        .where(Ticket.promoter_id == p.id)
    ).one()
    tickets_sold = int(agg[0] or 0)
    revenue = Decimal(agg[1] or 0)
    commission = (revenue * (p.commission_pct or Decimal(0)) / Decimal(100)).quantize(Decimal("0.01"))
    return PromoterOut(
        id=p.id,
        name=p.name,
        slug=p.slug,
        phone=p.phone,
        commission_pct=p.commission_pct or Decimal(0),
        active=p.active,
        tickets_sold=tickets_sold,
        revenue=revenue,
        commission_amount=commission,
    )
