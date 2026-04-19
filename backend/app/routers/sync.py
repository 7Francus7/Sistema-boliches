from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user
from ..models import (
    AccessLog,
    Sale,
    SaleItem,
    StockLevel,
    StockMovement,
    Ticket,
    User,
)
from ..schemas import (
    AccessOp,
    OpResult,
    SaleOp,
    StockOp,
    SyncBatchIn,
    SyncBatchOut,
)

router = APIRouter(prefix="/sync", tags=["sync"])


def _apply_sale(db: Session, op: SaleOp, user: User) -> OpResult:
    existing = db.execute(select(Sale).where(Sale.client_uuid == op.client_uuid)).scalar_one_or_none()
    if existing:
        return OpResult(client_uuid=op.client_uuid, status="duplicate", server_id=existing.id)

    sale = Sale(
        client_uuid=op.client_uuid,
        event_id=op.event_id,
        device_id=op.device_id,
        user_id=user.id,
        total=op.total,
        payment_method=op.payment_method,
        created_at=op.created_at,
    )
    db.add(sale)
    db.flush()

    for it in op.items:
        db.add(
            SaleItem(
                sale_id=sale.id,
                product_id=it.product_id,
                qty=it.qty,
                unit_price=it.unit_price,
                discount=it.discount,
            )
        )
        # Log de movimiento: egreso de stock atado a la venta.
        # qty_delta negativo porque sale del inventario.
        mov = StockMovement(
            client_uuid=op.client_uuid,  # 1 venta = 1 movimiento por ítem seria ideal, simplificado acá
            product_id=it.product_id,
            event_id=op.event_id,
            type="out",
            qty_delta=-it.qty,
            ref_sale_id=sale.id,
            reason="sale",
        )
        db.add(mov)

        level = db.get(StockLevel, it.product_id)
        if level is None:
            level = StockLevel(product_id=it.product_id, venue_id=user.venue_id, qty_on_hand=0)
            db.add(level)
        level.qty_on_hand = (level.qty_on_hand or 0) - it.qty

    return OpResult(client_uuid=op.client_uuid, status="accepted", server_id=sale.id)


def _apply_access(db: Session, op: AccessOp) -> OpResult:
    existing = db.execute(
        select(AccessLog).where(AccessLog.client_uuid == op.client_uuid)
    ).scalar_one_or_none()
    if existing:
        return OpResult(client_uuid=op.client_uuid, status="duplicate", server_id=existing.id)

    ticket = db.get(Ticket, op.ticket_id)
    if ticket is None:
        return OpResult(client_uuid=op.client_uuid, status="error", reason="ticket_not_found")

    if op.direction == "in":
        if ticket.status == "void":
            return OpResult(client_uuid=op.client_uuid, status="conflict", reason="ticket_void")
        if ticket.status == "used":
            # First-write-wins por scanned_at: el segundo escaneo es conflicto.
            if ticket.used_at and ticket.used_at <= op.scanned_at:
                return OpResult(
                    client_uuid=op.client_uuid, status="conflict", reason="already_used"
                )
        ticket.status = "used"
        ticket.used_at = op.scanned_at
        ticket.used_by_device_id = op.device_id

    log = AccessLog(
        client_uuid=op.client_uuid,
        ticket_id=op.ticket_id,
        event_id=op.event_id,
        device_id=op.device_id,
        direction=op.direction,
        scanned_at=op.scanned_at,
    )
    db.add(log)
    db.flush()
    return OpResult(client_uuid=op.client_uuid, status="accepted", server_id=log.id)


def _apply_stock(db: Session, op: StockOp, user: User) -> OpResult:
    existing = db.execute(
        select(StockMovement).where(StockMovement.client_uuid == op.client_uuid)
    ).scalar_one_or_none()
    if existing:
        return OpResult(client_uuid=op.client_uuid, status="duplicate", server_id=existing.id)

    mov = StockMovement(
        client_uuid=op.client_uuid,
        product_id=op.product_id,
        event_id=op.event_id,
        type=op.type,
        qty_delta=op.qty_delta,
        reason=op.reason,
    )
    db.add(mov)
    db.flush()

    level = db.get(StockLevel, op.product_id)
    if level is None:
        level = StockLevel(product_id=op.product_id, venue_id=user.venue_id, qty_on_hand=0)
        db.add(level)
    level.qty_on_hand = (level.qty_on_hand or 0) + op.qty_delta
    return OpResult(client_uuid=op.client_uuid, status="accepted", server_id=mov.id)


@router.post("/batch", response_model=SyncBatchOut)
def sync_batch(
    body: SyncBatchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyncBatchOut:
    """Aplica operaciones generadas offline. Idempotente por client_uuid."""
    results: list[OpResult] = []

    for op in body.ops:
        try:
            if isinstance(op, SaleOp):
                res = _apply_sale(db, op, user)
            elif isinstance(op, AccessOp):
                res = _apply_access(db, op)
            elif isinstance(op, StockOp):
                res = _apply_stock(db, op, user)
            else:  # pragma: no cover
                res = OpResult(client_uuid=op.client_uuid, status="error", reason="unknown_op")
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            res = OpResult(client_uuid=op.client_uuid, status="error", reason=str(exc)[:200])
        results.append(res)

    db.commit()
    return SyncBatchOut(results=results, server_time=datetime.now(timezone.utc))
