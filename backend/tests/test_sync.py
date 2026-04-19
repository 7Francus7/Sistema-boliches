"""Tests clave del flujo offline-first.

Validamos:
 - idempotencia por client_uuid (mandar 2x la misma venta → 1 sola aplicada)
 - conflicto de QR (2 dispositivos escanean el mismo ticket)
 - stock decrementa correctamente
 - flujo completo: ventas offline → sync → dashboard refleja
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from tests.conftest import auth_headers, login


def _register_device(client, token, label="Barra", kind="pos"):
    r = client.post(
        "/devices/register",
        json={"label": label, "type": kind},
        headers=auth_headers(token),
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _sale_op(event_id, device_id, product_id, qty=2, price="8000", cuuid=None):
    return {
        "kind": "sale",
        "client_uuid": cuuid or str(uuid.uuid4()),
        "event_id": event_id,
        "device_id": device_id,
        "total": f"{int(price) * qty}",
        "payment_method": "cash",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "items": [
            {"product_id": product_id, "qty": qty, "unit_price": price, "discount": "0"},
        ],
    }


def test_sync_sale_idempotent(seeded):
    client, data = seeded
    tok = login(client, data["cashier_email"])["access_token"]
    dev = _register_device(client, tok)

    op = _sale_op(data["event_id"], dev, data["product_id"], qty=3)

    # Primer envío
    r1 = client.post(
        "/sync/batch",
        json={"device_id": dev, "ops": [op]},
        headers=auth_headers(tok),
    )
    assert r1.status_code == 200
    assert r1.json()["results"][0]["status"] == "accepted"

    # Reenvío del mismo client_uuid → duplicate, no se re-procesa
    r2 = client.post(
        "/sync/batch",
        json={"device_id": dev, "ops": [op]},
        headers=auth_headers(tok),
    )
    assert r2.json()["results"][0]["status"] == "duplicate"

    # Dashboard: una sola venta, no dos
    tok_admin = login(client, data["admin_email"])["access_token"]
    dash = client.get("/analytics/dashboard", headers=auth_headers(tok_admin)).json()
    assert dash["sales_count"] == 1
    assert dash["revenue_total"] == 24000.0  # 3 x 8000


def test_sync_stock_decrements(seeded):
    client, data = seeded
    tok = login(client, data["cashier_email"])["access_token"]
    dev = _register_device(client, tok)

    ops = [_sale_op(data["event_id"], dev, data["product_id"], qty=5) for _ in range(3)]
    r = client.post(
        "/sync/batch",
        json={"device_id": dev, "ops": ops},
        headers=auth_headers(tok),
    )
    assert all(x["status"] == "accepted" for x in r.json()["results"])

    # Stock cae: 50 - 15 = 35
    tok_admin = login(client, data["admin_email"])["access_token"]
    products = client.get("/products", headers=auth_headers(tok_admin)).json()
    assert products[0]["qty_on_hand"] == 35


def test_access_first_write_wins(seeded):
    """Dos devices escanean el mismo QR. El segundo recibe 'conflict'."""
    client, data = seeded
    tok = login(client, data["cashier_email"])["access_token"]
    dev_a = _register_device(client, tok, "Puerta A", "door")
    dev_b = _register_device(client, tok, "Puerta B", "door")

    t = data["tickets"][0]
    earlier = datetime(2026, 1, 1, 22, 0, 0, tzinfo=timezone.utc).isoformat()
    later = datetime(2026, 1, 1, 22, 0, 5, tzinfo=timezone.utc).isoformat()

    op_a = {
        "kind": "access",
        "client_uuid": str(uuid.uuid4()),
        "ticket_id": t["id"],
        "event_id": data["event_id"],
        "device_id": dev_a,
        "direction": "in",
        "scanned_at": earlier,
    }
    op_b = {
        "kind": "access",
        "client_uuid": str(uuid.uuid4()),
        "ticket_id": t["id"],
        "event_id": data["event_id"],
        "device_id": dev_b,
        "direction": "in",
        "scanned_at": later,
    }

    r = client.post(
        "/sync/batch",
        json={"device_id": dev_a, "ops": [op_a, op_b]},
        headers=auth_headers(tok),
    )
    results = r.json()["results"]
    assert results[0]["status"] == "accepted"
    assert results[1]["status"] == "conflict"
    assert results[1]["reason"] == "already_used"


def test_access_invalid_ticket(seeded):
    client, data = seeded
    tok = login(client, data["cashier_email"])["access_token"]
    dev = _register_device(client, tok, "Puerta", "door")

    op = {
        "kind": "access",
        "client_uuid": str(uuid.uuid4()),
        "ticket_id": str(uuid.uuid4()),  # no existe
        "event_id": data["event_id"],
        "device_id": dev,
        "direction": "in",
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }
    r = client.post(
        "/sync/batch",
        json={"device_id": dev, "ops": [op]},
        headers=auth_headers(tok),
    )
    assert r.json()["results"][0]["status"] == "error"
    assert "ticket_not_found" in r.json()["results"][0]["reason"]


def test_offline_simulation_full_flow(seeded):
    """Simula el camino completo: cliente offline acumula ops → vuelve online → sync → dashboard."""
    client, data = seeded
    tok = login(client, data["cashier_email"])["access_token"]
    dev = _register_device(client, tok)

    # "Offline": acumulamos 5 ventas en la 'outbox' del cliente (acá solo una lista).
    outbox = []
    for _ in range(5):
        outbox.append(_sale_op(data["event_id"], dev, data["product_id"], qty=1))

    # "Online": se drena todo en un batch.
    r = client.post(
        "/sync/batch",
        json={"device_id": dev, "ops": outbox},
        headers=auth_headers(tok),
    )
    results = r.json()["results"]
    assert len(results) == 5
    assert all(x["status"] == "accepted" for x in results)

    tok_admin = login(client, data["admin_email"])["access_token"]
    dash = client.get("/analytics/dashboard", headers=auth_headers(tok_admin)).json()
    assert dash["sales_count"] == 5
    assert dash["revenue_total"] == 5 * 8000
