"""Turnos: apertura, cierre con arqueo, variance detectada."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from tests.conftest import auth_headers, login


def _register_device(client, token):
    return client.post(
        "/devices/register", json={"label": "Barra", "type": "pos"},
        headers=auth_headers(token),
    ).json()["id"]


def _sale(client, token, event_id, device_id, product_id, method="cash", amount="8000"):
    op = {
        "kind": "sale",
        "client_uuid": str(uuid.uuid4()),
        "event_id": event_id,
        "device_id": device_id,
        "total": amount,
        "payment_method": method,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "items": [{"product_id": product_id, "qty": 1, "unit_price": amount, "discount": "0"}],
    }
    return client.post(
        "/sync/batch", json={"device_id": device_id, "ops": [op]},
        headers=auth_headers(token),
    )


def test_open_close_shift_cash_match(seeded):
    client, data = seeded
    tok = login(client, data["cashier_email"])["access_token"]
    dev = _register_device(client, tok)

    r = client.post(
        "/shifts/open",
        json={"device_id": dev, "event_id": data["event_id"], "opening_cash": "10000"},
        headers=auth_headers(tok),
    )
    assert r.status_code == 200
    sid = r.json()["id"]

    # 3 ventas efectivo de 8000 + 1 tarjeta
    for _ in range(3):
        _sale(client, tok, data["event_id"], dev, data["product_id"], method="cash")
    _sale(client, tok, data["event_id"], dev, data["product_id"], method="card")

    # Cierre con efectivo "perfecto" (apertura 10000 + 3*8000 = 34000)
    r = client.post(
        f"/shifts/{sid}/close",
        json={"closing_cash": "34000", "notes": "cierre normal"},
        headers=auth_headers(tok),
    )
    body = r.json()
    assert body["expected_cash"] == "34000.00"
    assert body["cash_variance"] == "0.00"
    assert body["closed_at"] is not None


def test_shift_detects_cash_variance(seeded):
    """Si falta plata al cerrar, variance queda negativa: señal de merma/robo."""
    client, data = seeded
    tok = login(client, data["cashier_email"])["access_token"]
    dev = _register_device(client, tok)

    sid = client.post(
        "/shifts/open", json={"device_id": dev, "opening_cash": "0"},
        headers=auth_headers(tok),
    ).json()["id"]

    for _ in range(5):
        _sale(client, tok, data["event_id"], dev, data["product_id"], method="cash")

    # Esperado 40000, pero cerramos declarando 35000 (faltan 5k)
    r = client.post(
        f"/shifts/{sid}/close",
        json={"closing_cash": "35000"},
        headers=auth_headers(tok),
    )
    body = r.json()
    assert float(body["expected_cash"]) == 40000.0
    assert float(body["cash_variance"]) == -5000.0


def test_cannot_double_open(seeded):
    client, data = seeded
    tok = login(client, data["cashier_email"])["access_token"]
    dev = _register_device(client, tok)
    client.post(
        "/shifts/open", json={"device_id": dev, "opening_cash": "0"},
        headers=auth_headers(tok),
    )
    r = client.post(
        "/shifts/open", json={"device_id": dev, "opening_cash": "0"},
        headers=auth_headers(tok),
    )
    assert r.status_code == 409


def test_shift_close_report(seeded):
    client, data = seeded
    tok = login(client, data["cashier_email"])["access_token"]
    admin_tok = login(client, data["admin_email"])["access_token"]
    dev = _register_device(client, tok)

    sid = client.post(
        "/shifts/open", json={"device_id": dev, "opening_cash": "0"},
        headers=auth_headers(tok),
    ).json()["id"]
    for _ in range(2):
        _sale(client, tok, data["event_id"], dev, data["product_id"], method="cash")
    client.post(
        f"/shifts/{sid}/close", json={"closing_cash": "16000"},
        headers=auth_headers(tok),
    )
    rep = client.get(f"/analytics/shift-close/{sid}", headers=auth_headers(admin_tok)).json()
    assert rep["cash_variance"] == 0
    assert any(m["method"] == "cash" and m["count"] == 2 for m in rep["sales_by_method"])
    assert rep["items_sold"][0]["units"] == 2
