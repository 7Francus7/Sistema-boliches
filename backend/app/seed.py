"""Seed idempotente para desarrollo. Crea un venue demo, usuarios, evento y productos."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from .db import SessionLocal
from .models import (
    Device,
    Event,
    Product,
    StockLevel,
    Ticket,
    TicketType,
    User,
    Venue,
)
from .security import hash_password, sign_ticket_qr


DEMO_EMAIL_ADMIN = "admin@demo.local"
DEMO_EMAIL_CASHIER = "cajero@demo.local"
DEMO_EMAIL_DOOR = "puerta@demo.local"


def run_seed() -> None:
    db = SessionLocal()
    try:
        if db.execute(select(User).where(User.email == DEMO_EMAIL_ADMIN)).first():
            return

        venue = Venue(name="Boliche Demo", capacity_max=500)
        db.add(venue)
        db.flush()

        db.add_all(
            [
                User(
                    venue_id=venue.id,
                    email=DEMO_EMAIL_ADMIN,
                    password_hash=hash_password("admin123"),
                    role="admin",
                    pin_code="1111",
                ),
                User(
                    venue_id=venue.id,
                    email=DEMO_EMAIL_CASHIER,
                    password_hash=hash_password("cajero123"),
                    role="cashier",
                    pin_code="2222",
                ),
                User(
                    venue_id=venue.id,
                    email=DEMO_EMAIL_DOOR,
                    password_hash=hash_password("puerta123"),
                    role="door",
                    pin_code="3333",
                ),
            ]
        )

        db.add_all(
            [
                Device(venue_id=venue.id, label="Barra Central", type="pos"),
                Device(venue_id=venue.id, label="Puerta Principal", type="door"),
            ]
        )

        now = datetime.now(timezone.utc)
        event = Event(
            venue_id=venue.id,
            name="Noche Demo",
            starts_at=now,
            ends_at=now + timedelta(hours=8),
            status="live",
            capacity_override=500,
        )
        db.add(event)
        db.flush()

        tt_general = TicketType(event_id=event.id, name="General", price=Decimal("5000"), quota=300)
        tt_vip = TicketType(event_id=event.id, name="VIP", price=Decimal("12000"), quota=50, color_tag="#ef4444")
        db.add_all([tt_general, tt_vip])
        db.flush()

        # Entradas demo (20 general + 5 vip)
        for _ in range(20):
            tid = uuid.uuid4()
            db.add(
                Ticket(
                    id=tid,
                    event_id=event.id,
                    ticket_type_id=tt_general.id,
                    qr_code=sign_ticket_qr(str(tid), str(event.id)),
                )
            )
        for _ in range(5):
            tid = uuid.uuid4()
            db.add(
                Ticket(
                    id=tid,
                    event_id=event.id,
                    ticket_type_id=tt_vip.id,
                    qr_code=sign_ticket_qr(str(tid), str(event.id)),
                )
            )

        products = [
            ("FE-750", "Fernet 750ml", Decimal("8000"), 120),
            ("CC-LATA", "Coca-Cola lata", Decimal("2500"), 300),
            ("CERV-IPA", "Cerveza IPA pinta", Decimal("4500"), 200),
            ("VODKA-SHOT", "Vodka shot", Decimal("3000"), 150),
            ("AGUA-500", "Agua 500ml", Decimal("1500"), 200),
            ("RB-LATA", "Red Bull", Decimal("4000"), 180),
        ]
        for sku, name, price, stock in products:
            p = Product(
                venue_id=venue.id,
                sku=sku,
                name=name,
                sale_price=price,
                cost_price=price / 2,
            )
            db.add(p)
            db.flush()
            db.add(StockLevel(product_id=p.id, venue_id=venue.id, qty_on_hand=stock))

        db.commit()
        print(f"[seed] venue={venue.id} admin={DEMO_EMAIL_ADMIN}/admin123 event={event.id}")
    finally:
        db.close()
