from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user
from ..models import Event, Product, StockLevel, Ticket, User
from ..schemas import BootstrapOut, EventOut, ProductOut, TicketLite

router = APIRouter(prefix="/bootstrap", tags=["bootstrap"])


@router.get("", response_model=BootstrapOut)
def bootstrap(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> BootstrapOut:
    """Pre-carga para que el dispositivo pueda operar offline toda la noche."""
    now = datetime.now(timezone.utc)

    event = db.execute(
        select(Event)
        .where(Event.venue_id == user.venue_id, Event.status.in_(("live", "draft")))
        .order_by(Event.starts_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    products_rows = db.execute(
        select(Product, StockLevel.qty_on_hand)
        .join(StockLevel, StockLevel.product_id == Product.id, isouter=True)
        .where(Product.venue_id == user.venue_id, Product.active.is_(True))
    ).all()

    products = [
        ProductOut(
            id=p.id,
            sku=p.sku,
            name=p.name,
            category=p.category,
            sale_price=p.sale_price,
            qty_on_hand=qty or 0,
        )
        for p, qty in products_rows
    ]

    tickets: list[TicketLite] = []
    if event is not None:
        t_rows = db.execute(select(Ticket).where(Ticket.event_id == event.id)).scalars().all()
        tickets = [
            TicketLite(id=t.id, qr_code=t.qr_code, ticket_type_id=t.ticket_type_id, status=t.status)
            for t in t_rows
        ]

    event_out = None
    if event is not None:
        event_out = EventOut(
            id=event.id,
            name=event.name,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
            capacity=event.capacity_override or 500,
            status=event.status,
        )

    return BootstrapOut(
        venue_id=user.venue_id,
        event=event_out,
        products=products,
        tickets=tickets,
        server_time=now,
    )
