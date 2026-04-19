from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_roles
from ..models import (
    Product,
    Purchase,
    PurchaseItem,
    StockLevel,
    Supplier,
    User,
)

router = APIRouter(tags=["suppliers"])


class SupplierIn(BaseModel):
    name: str
    contact: str | None = None
    phone: str | None = None
    email: str | None = None
    tax_id: str | None = None


class SupplierOut(BaseModel):
    id: uuid.UUID
    name: str
    contact: str | None
    phone: str | None
    email: str | None
    tax_id: str | None
    active: bool


@router.post("/suppliers", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
def create_supplier(
    body: SupplierIn,
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    s = Supplier(venue_id=user.venue_id, **body.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return SupplierOut(**_sup_dict(s))


@router.get("/suppliers", response_model=list[SupplierOut])
def list_suppliers(user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Supplier).where(Supplier.venue_id == user.venue_id)
    ).scalars().all()
    return [SupplierOut(**_sup_dict(s)) for s in rows]


def _sup_dict(s: Supplier) -> dict:
    return {
        "id": s.id, "name": s.name, "contact": s.contact,
        "phone": s.phone, "email": s.email, "tax_id": s.tax_id, "active": s.active,
    }


# -------- Purchases --------

class PurchaseItemIn(BaseModel):
    product_id: uuid.UUID
    qty: int
    unit_cost: Decimal


class PurchaseIn(BaseModel):
    supplier_id: uuid.UUID
    reference: str | None = None
    items: list[PurchaseItemIn]


class PurchaseItemOut(BaseModel):
    product_id: uuid.UUID
    qty: int
    unit_cost: Decimal


class PurchaseOut(BaseModel):
    id: uuid.UUID
    supplier_id: uuid.UUID
    reference: str | None
    total: Decimal
    received_at: datetime
    items: list[PurchaseItemOut]


@router.post("/purchases", response_model=PurchaseOut, status_code=status.HTTP_201_CREATED)
def create_purchase(
    body: PurchaseIn,
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    sup = db.get(Supplier, body.supplier_id)
    if not sup or sup.venue_id != user.venue_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "proveedor no encontrado")

    p = Purchase(
        venue_id=user.venue_id,
        supplier_id=body.supplier_id,
        reference=body.reference,
        user_id=user.id,
        total=Decimal("0"),
    )
    db.add(p)
    db.flush()

    total = Decimal("0")
    for it in body.items:
        prod = db.get(Product, it.product_id)
        if not prod or prod.venue_id != user.venue_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"producto {it.product_id} inválido")

        db.add(PurchaseItem(
            purchase_id=p.id,
            product_id=it.product_id,
            qty=it.qty,
            unit_cost=it.unit_cost,
        ))

        # Actualiza stock_levels (+qty).
        lvl = db.get(StockLevel, it.product_id)
        if lvl is None:
            lvl = StockLevel(product_id=it.product_id, venue_id=user.venue_id, qty_on_hand=0)
            db.add(lvl)
        lvl.qty_on_hand = (lvl.qty_on_hand or 0) + it.qty

        # Actualiza costo promedio ponderado: (stock_existente * costo_actual + qty*unit_cost) / (stock_existente + qty)
        existing_qty = lvl.qty_on_hand - it.qty
        if existing_qty < 0:
            existing_qty = 0
        if existing_qty == 0:
            prod.cost_price = it.unit_cost
        else:
            prod.cost_price = (
                (Decimal(existing_qty) * (prod.cost_price or Decimal(0)) + Decimal(it.qty) * it.unit_cost)
                / Decimal(existing_qty + it.qty)
            ).quantize(Decimal("0.01"))

        total += Decimal(it.qty) * it.unit_cost

    p.total = total
    db.commit()
    db.refresh(p)

    return PurchaseOut(
        id=p.id,
        supplier_id=p.supplier_id,
        reference=p.reference,
        total=p.total,
        received_at=p.received_at,
        items=[PurchaseItemOut(product_id=i.product_id, qty=i.qty, unit_cost=i.unit_cost) for i in p.items],
    )


@router.get("/purchases", response_model=list[PurchaseOut])
def list_purchases(user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Purchase).where(Purchase.venue_id == user.venue_id)
        .order_by(Purchase.received_at.desc()).limit(100)
    ).scalars().all()
    return [
        PurchaseOut(
            id=p.id,
            supplier_id=p.supplier_id,
            reference=p.reference,
            total=p.total,
            received_at=p.received_at,
            items=[PurchaseItemOut(product_id=i.product_id, qty=i.qty, unit_cost=i.unit_cost) for i in p.items],
        )
        for p in rows
    ]
