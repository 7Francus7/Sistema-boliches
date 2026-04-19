import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_roles
from ..models import Product, StockLevel, StockMovement, User
from ..schemas import ProductOut

router = APIRouter(prefix="/products", tags=["products"])


class ProductIn(BaseModel):
    sku: str
    name: str
    category: str = "barra"
    sale_price: Decimal
    cost_price: Decimal = Decimal("0")
    initial_stock: int = 0


class StockAdjustIn(BaseModel):
    qty_delta: int
    reason: str | None = None


@router.get("", response_model=list[ProductOut])
def list_products(
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(Product, StockLevel.qty_on_hand)
        .join(StockLevel, StockLevel.product_id == Product.id, isouter=True)
        .where(Product.venue_id == user.venue_id)
    ).all()
    return [
        ProductOut(
            id=p.id,
            sku=p.sku,
            name=p.name,
            category=p.category,
            sale_price=p.sale_price,
            qty_on_hand=qty or 0,
        )
        for p, qty in rows
    ]


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    body: ProductIn,
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    p = Product(
        venue_id=user.venue_id,
        sku=body.sku,
        name=body.name,
        category=body.category,
        sale_price=body.sale_price,
        cost_price=body.cost_price,
    )
    db.add(p)
    try:
        db.flush()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "sku duplicado") from exc

    db.add(StockLevel(product_id=p.id, venue_id=user.venue_id, qty_on_hand=body.initial_stock))
    db.commit()
    db.refresh(p)
    return ProductOut(
        id=p.id, sku=p.sku, name=p.name, category=p.category,
        sale_price=p.sale_price, qty_on_hand=body.initial_stock,
    )


@router.put("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: str,
    body: ProductIn,
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    pid = _parse_uuid(product_id)
    p = db.get(Product, pid)
    if not p or p.venue_id != user.venue_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "producto no encontrado")
    p.sku = body.sku
    p.name = body.name
    p.category = body.category
    p.sale_price = body.sale_price
    p.cost_price = body.cost_price
    db.commit()
    level = db.get(StockLevel, pid)
    return ProductOut(
        id=p.id, sku=p.sku, name=p.name, category=p.category,
        sale_price=p.sale_price, qty_on_hand=(level.qty_on_hand if level else 0),
    )


def _parse_uuid(v: str) -> uuid.UUID:
    try:
        return uuid.UUID(v)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "id inválido")


@router.post("/{product_id}/stock", response_model=ProductOut)
def adjust_stock(
    product_id: str,
    body: StockAdjustIn,
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Ajuste manual de stock desde la UI admin. Genera un stock_movement trazable."""
    pid = _parse_uuid(product_id)
    p = db.get(Product, pid)
    if not p or p.venue_id != user.venue_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "producto no encontrado")

    level = db.get(StockLevel, pid)
    if level is None:
        level = StockLevel(product_id=pid, venue_id=user.venue_id, qty_on_hand=0)
        db.add(level)
    level.qty_on_hand = (level.qty_on_hand or 0) + body.qty_delta

    db.add(
        StockMovement(
            client_uuid=uuid.uuid4(),
            product_id=pid,
            type="adjust" if body.qty_delta != 0 else "in",
            qty_delta=body.qty_delta,
            reason=body.reason or "ajuste manual",
        )
    )
    db.commit()
    return ProductOut(
        id=p.id, sku=p.sku, name=p.name, category=p.category,
        sale_price=p.sale_price, qty_on_hand=level.qty_on_hand,
    )
