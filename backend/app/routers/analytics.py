from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_roles
from ..models import (
    AccessLog,
    Product,
    Promoter,
    Sale,
    SaleItem,
    Shift,
    StockLevel,
    Ticket,
    TicketType,
    User,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard")
def dashboard(
    event_id: str | None = None,
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    sale_filter = [Sale.user_id.is_not(None)]
    if event_id:
        sale_filter.append(Sale.event_id == event_id)

    total = db.execute(
        select(func.coalesce(func.sum(Sale.total), 0)).where(*sale_filter)
    ).scalar()
    count = db.execute(
        select(func.count(Sale.id)).where(*sale_filter)
    ).scalar() or 0
    avg_ticket = float(total) / count if count else 0

    top_products = db.execute(
        select(
            Product.name,
            func.sum(SaleItem.qty).label("units"),
            func.sum(SaleItem.qty * SaleItem.unit_price).label("revenue"),
            func.sum(SaleItem.qty * (SaleItem.unit_price - Product.cost_price)).label("margin"),
        )
        .join(SaleItem, SaleItem.product_id == Product.id)
        .group_by(Product.name)
        .order_by(func.sum(SaleItem.qty).desc())
        .limit(10)
    ).all()

    # Ranking de cajeros.
    cashiers = db.execute(
        select(
            User.email,
            func.count(Sale.id).label("sales_count"),
            func.coalesce(func.sum(Sale.total), 0).label("revenue"),
        )
        .join(Sale, Sale.user_id == User.id)
        .group_by(User.email)
        .order_by(func.coalesce(func.sum(Sale.total), 0).desc())
    ).all()

    since = datetime.now(timezone.utc) - timedelta(hours=12)
    dialect = db.bind.dialect.name if db.bind else "postgresql"
    if dialect == "sqlite":
        hour_expr = func.strftime("%Y-%m-%d %H:00:00", AccessLog.scanned_at).label("h")
    else:
        hour_expr = func.date_trunc("hour", AccessLog.scanned_at).label("h")
    access_by_hour = db.execute(
        select(hour_expr, func.count(AccessLog.id))
        .where(AccessLog.scanned_at >= since, AccessLog.direction == "in")
        .group_by(hour_expr)
        .order_by(hour_expr)
    ).all()

    def _fmt_hour(h):
        if h is None:
            return None
        return h.isoformat() if hasattr(h, "isoformat") else str(h)

    return {
        "revenue_total": float(total or 0),
        "sales_count": count,
        "avg_ticket": round(avg_ticket, 2),
        "top_products": [
            {
                "name": n,
                "units": int(u or 0),
                "revenue": float(r or 0),
                "margin": float(m or 0),
            }
            for n, u, r, m in top_products
        ],
        "cashier_ranking": [
            {"email": e, "sales": int(c or 0), "revenue": float(r or 0)}
            for e, c, r in cashiers
        ],
        "access_by_hour": [{"hour": _fmt_hour(h), "count": c} for h, c in access_by_hour],
    }


@router.get("/commissions")
def commissions(
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Liquidación de comisiones por RRPP: cuántos tickets vendió y cuánto cobra."""
    rows = db.execute(
        select(
            Promoter.id,
            Promoter.name,
            Promoter.commission_pct,
            func.count(Ticket.id).label("tickets"),
            func.coalesce(func.sum(TicketType.price), 0).label("revenue"),
        )
        .join(Ticket, Ticket.promoter_id == Promoter.id, isouter=True)
        .join(TicketType, TicketType.id == Ticket.ticket_type_id, isouter=True)
        .where(Promoter.venue_id == user.venue_id)
        .group_by(Promoter.id, Promoter.name, Promoter.commission_pct)
    ).all()

    out = []
    for pid, name, pct, tickets, revenue in rows:
        pct_d = Decimal(pct or 0)
        rev_d = Decimal(revenue or 0)
        commission = (rev_d * pct_d / Decimal(100)).quantize(Decimal("0.01"))
        out.append({
            "promoter_id": str(pid),
            "name": name,
            "commission_pct": float(pct_d),
            "tickets_sold": int(tickets or 0),
            "revenue": float(rev_d),
            "commission_amount": float(commission),
        })
    return out


@router.get("/low-stock")
def low_stock(
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(Product, StockLevel.qty_on_hand)
        .join(StockLevel, StockLevel.product_id == Product.id, isouter=True)
        .where(
            Product.venue_id == user.venue_id,
            Product.active.is_(True),
        )
    ).all()
    alerts = []
    for p, qty in rows:
        qty = qty or 0
        threshold = p.low_stock_threshold or 10
        if qty <= threshold:
            alerts.append({
                "product_id": str(p.id),
                "sku": p.sku,
                "name": p.name,
                "qty_on_hand": int(qty),
                "threshold": int(threshold),
                "severity": "critical" if qty <= 0 else ("low" if qty <= threshold / 2 else "warn"),
            })
    return alerts


@router.get("/sales.csv")
def sales_csv(
    event_id: str | None = None,
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Export CSV del detalle de ventas. Columnas pensadas para pegar en Excel."""
    q = select(
        Sale.id, Sale.created_at, Sale.payment_method, Sale.total,
        User.email, Product.name, SaleItem.qty, SaleItem.unit_price,
    ).join(SaleItem, SaleItem.sale_id == Sale.id) \
     .join(Product, Product.id == SaleItem.product_id) \
     .join(User, User.id == Sale.user_id)
    if event_id:
        q = q.where(Sale.event_id == event_id)
    rows = db.execute(q).all()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["sale_id", "created_at", "method", "total", "cashier", "product", "qty", "unit_price"])
    for sid, ts, method, total, email, prod, qty, price in rows:
        w.writerow([sid, ts.isoformat() if ts else "", method, total, email, prod, qty, price])

    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sales.csv"},
    )


@router.get("/shift-close/{shift_id}")
def shift_close_report(
    shift_id: str,
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Resumen 'arqueo Z' del turno: ingresos por método, productos vendidos, variance."""
    try:
        sid = uuid.UUID(shift_id)
    except (ValueError, TypeError):
        from fastapi import HTTPException, status as st
        raise HTTPException(st.HTTP_404_NOT_FOUND, "turno no encontrado")
    s = db.get(Shift, sid)
    if not s:
        from fastapi import HTTPException, status as st
        raise HTTPException(st.HTTP_404_NOT_FOUND, "turno no encontrado")

    by_method = db.execute(
        select(Sale.payment_method, func.count(Sale.id), func.coalesce(func.sum(Sale.total), 0))
        .where(Sale.shift_id == sid)
        .group_by(Sale.payment_method)
    ).all()
    items = db.execute(
        select(Product.name, func.sum(SaleItem.qty), func.sum(SaleItem.qty * SaleItem.unit_price))
        .join(Sale, Sale.id == SaleItem.sale_id)
        .join(Product, Product.id == SaleItem.product_id)
        .where(Sale.shift_id == sid)
        .group_by(Product.name)
        .order_by(func.sum(SaleItem.qty).desc())
    ).all()

    return {
        "shift_id": str(s.id),
        "opened_at": s.opened_at.isoformat() if s.opened_at else None,
        "closed_at": s.closed_at.isoformat() if s.closed_at else None,
        "opening_cash": float(s.opening_cash or 0),
        "closing_cash": float(s.closing_cash or 0) if s.closing_cash is not None else None,
        "expected_cash": float(s.expected_cash or 0) if s.expected_cash is not None else None,
        "cash_variance": float(s.cash_variance or 0) if s.cash_variance is not None else None,
        "sales_by_method": [
            {"method": m, "count": int(c or 0), "total": float(t or 0)} for m, c, t in by_method
        ],
        "items_sold": [
            {"product": n, "units": int(u or 0), "revenue": float(r or 0)} for n, u, r in items
        ],
    }
