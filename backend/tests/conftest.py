"""Fixtures comunes: app aislada con SQLite en memoria + cliente httpx."""
from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("ENV", "test")

from app import db as app_db  # noqa: E402
from app.db import Base  # noqa: E402
from app import main as app_main  # noqa: E402
from app.security import hash_password, sign_ticket_qr  # noqa: E402


@pytest.fixture()
def test_app(tmp_path, monkeypatch):
    # Usamos SQLite por test para aislar y no depender de Postgres ni alembic.
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    monkeypatch.setattr(app_db, "engine", engine)
    monkeypatch.setattr(app_db, "SessionLocal", TestingSession)

    # Evitamos alembic + seed en tests: create_all directo contra SQLite.
    Base.metadata.create_all(bind=engine)

    # Reemplazamos el lifespan: no corre migraciones ni seed.
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_lifespan(app):
        yield

    monkeypatch.setattr(app_main, "lifespan", fake_lifespan)

    # Reconstruimos el app con el lifespan nuevo:
    # como FastAPI ya tiene el lifespan seteado al importar, basta con que
    # el cliente TestClient use el existente (los tests no lo disparan si no
    # envolvemos con "with"). Por eso NO usamos "with TestClient" más abajo.
    client = TestClient(app_main.app)
    yield client, TestingSession


@pytest.fixture()
def seeded(test_app):
    """Crea venue + admin + productos + evento + tickets para un test."""
    from app.models import (
        Event,
        Product,
        StockLevel,
        Ticket,
        TicketType,
        User,
        Venue,
    )
    from datetime import datetime, timedelta, timezone
    from decimal import Decimal

    client, Session = test_app
    db = Session()
    venue = Venue(name="Test Club", capacity_max=200)
    db.add(venue)
    db.flush()

    admin = User(
        venue_id=venue.id,
        email="a@t.local",
        password_hash=hash_password("pw"),
        role="admin",
    )
    cashier = User(
        venue_id=venue.id,
        email="c@t.local",
        password_hash=hash_password("pw"),
        role="cashier",
    )
    db.add_all([admin, cashier])
    db.flush()

    now = datetime.now(timezone.utc)
    event = Event(
        venue_id=venue.id,
        name="Noche Test",
        starts_at=now,
        ends_at=now + timedelta(hours=6),
        status="live",
        capacity_override=200,
    )
    db.add(event)
    db.flush()

    tt = TicketType(event_id=event.id, name="General", price=Decimal("5000"), quota=100)
    db.add(tt)
    db.flush()

    tickets = []
    for _ in range(3):
        tid = uuid.uuid4()
        t = Ticket(
            id=tid,
            event_id=event.id,
            ticket_type_id=tt.id,
            qr_code=sign_ticket_qr(str(tid), str(event.id)),
        )
        db.add(t)
        tickets.append(t)

    p = Product(
        venue_id=venue.id,
        sku="FE-750",
        name="Fernet 750",
        sale_price=Decimal("8000"),
        cost_price=Decimal("4000"),
    )
    db.add(p)
    db.flush()
    db.add(StockLevel(product_id=p.id, venue_id=venue.id, qty_on_hand=50))
    db.commit()

    data = {
        "venue_id": str(venue.id),
        "admin_email": admin.email,
        "cashier_email": cashier.email,
        "event_id": str(event.id),
        "product_id": str(p.id),
        "tickets": [{"id": str(t.id), "qr": t.qr_code} for t in tickets],
    }
    db.close()
    return client, data


def login(client, email, password="pw"):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}
