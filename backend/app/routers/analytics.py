from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_roles
from ..models import AccessLog, Product, Sale, SaleItem, User

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard")
def dashboard(
    event_id: str | None = None,
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Dashboard simple para el dueño: ventas, ticket promedio, top productos, ritmo de acceso."""
    q_sales = select(Sale).where(Sale.user_id == Sale.user_id)
    if event_id:
        q_sales = q_sales.where(Sale.event_id == event_id)

    total = db.execute(select(func.coalesce(func.sum(Sale.total), 0)).select_from(Sale)).scalar()
    count = db.execute(select(func.count(Sale.id)).select_from(Sale)).scalar() or 0
    avg_ticket = float(total) / count if count else 0

    top_products = db.execute(
        select(
            Product.name,
            func.sum(SaleItem.qty).label("units"),
            func.sum(SaleItem.qty * SaleItem.unit_price).label("revenue"),
        )
        .join(SaleItem, SaleItem.product_id == Product.id)
        .group_by(Product.name)
        .order_by(func.sum(SaleItem.qty).desc())
        .limit(10)
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
        if hasattr(h, "isoformat"):
            return h.isoformat()
        return str(h)

    return {
        "revenue_total": float(total or 0),
        "sales_count": count,
        "avg_ticket": round(avg_ticket, 2),
        "top_products": [
            {"name": n, "units": int(u or 0), "revenue": float(r or 0)} for n, u, r in top_products
        ],
        "access_by_hour": [{"hour": _fmt_hour(h), "count": c} for h, c in access_by_hour],
    }
