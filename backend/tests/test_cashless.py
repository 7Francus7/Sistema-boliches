"""Cashless: cargas + consumos, offline idempotente, sobregiro detectado."""
from __future__ import annotations

import uuid

from tests.conftest import auth_headers, login


def _register_device(client, token, kind="pos"):
    return client.post(
        "/devices/register", json={"label": kind, "type": kind},
        headers=auth_headers(token),
    ).json()["id"]


def test_tab_create_and_load(seeded):
    client, data = seeded
    tok = login(client, data["cashier_email"])["access_token"]

    r = client.post(
        "/tabs",
        json={"code": "PULS-001", "holder_name": "Matías", "initial_load": "5000"},
        headers=auth_headers(tok),
    )
    assert r.status_code == 201
    tid = r.json()["id"]
    assert r.json()["balance"] == "5000.00"

    # recarga online
    r = client.post(
        f"/tabs/{tid}/load",
        json={"amount": "3000"},
        headers=auth_headers(tok),
    )
    assert r.json()["balance"] == "8000.00"


def test_cashless_offline_flow_with_idempotency(seeded):
    """Barra offline: cobra varios tragos, reintenta el sync → saldo final correcto sin dobles."""
    client, data = seeded
    tok = login(client, data["cashier_email"])["access_token"]
    dev = _register_device(client, tok)

    # Pulsera con saldo inicial 10000
    tab = client.post(
        "/tabs",
        json={"code": "PULS-99", "holder_name": "Cliente Offline", "initial_load": "10000"},
        headers=auth_headers(tok),
    ).json()
    assert tab["balance"] == "10000.00"

    # 3 consumos offline de 2500 cada uno
    charge_ops = []
    for _ in range(3):
        charge_ops.append({
            "kind": "tab_charge",
            "client_uuid": str(uuid.uuid4()),
            "tab_code": "PULS-99",
            "amount": "2500",
        })

    # Primer envío
    r = client.post(
        "/sync/batch",
        json={"device_id": dev, "ops": charge_ops},
        headers=auth_headers(tok),
    )
    assert all(x["status"] == "accepted" for x in r.json()["results"])
    tab = client.get("/tabs/by-code/PULS-99", headers=auth_headers(tok)).json()
    assert tab["balance"] == "2500.00"  # 10000 - 3*2500

    # Reintento del mismo batch (simula red inestable) → duplicates, sin doble descuento
    r2 = client.post(
        "/sync/batch",
        json={"device_id": dev, "ops": charge_ops},
        headers=auth_headers(tok),
    )
    assert all(x["status"] == "duplicate" for x in r2.json()["results"])
    tab = client.get("/tabs/by-code/PULS-99", headers=auth_headers(tok)).json()
    assert tab["balance"] == "2500.00"  # no se movió


def test_cashless_overdraft_allowed_but_flagged(seeded):
    """Si dos barras offline cobran al mismo tiempo, el saldo puede caer a negativo.
    El server lo acepta (no podemos frenar al cliente) pero lo marca."""
    client, data = seeded
    tok = login(client, data["cashier_email"])["access_token"]
    dev = _register_device(client, tok)

    client.post(
        "/tabs",
        json={"code": "PULS-OVER", "initial_load": "1000"},
        headers=auth_headers(tok),
    )

    ops = [
        {"kind": "tab_charge", "client_uuid": str(uuid.uuid4()), "tab_code": "PULS-OVER", "amount": "700"},
        {"kind": "tab_charge", "client_uuid": str(uuid.uuid4()), "tab_code": "PULS-OVER", "amount": "700"},
    ]
    r = client.post(
        "/sync/batch",
        json={"device_id": dev, "ops": ops},
        headers=auth_headers(tok),
    )
    results = r.json()["results"]
    assert results[0]["status"] == "accepted"
    assert results[1]["status"] == "accepted"
    assert results[1]["reason"] == "overdraft"

    tab = client.get("/tabs/by-code/PULS-OVER", headers=auth_headers(tok)).json()
    assert tab["balance"] == "-400.00"


def test_tab_close_refunds_remainder(seeded):
    client, data = seeded
    tok = login(client, data["cashier_email"])["access_token"]
    tid = client.post(
        "/tabs", json={"code": "PULS-CLOSE", "initial_load": "5000"},
        headers=auth_headers(tok),
    ).json()["id"]

    r = client.post(f"/tabs/{tid}/close", headers=auth_headers(tok))
    assert r.json()["status"] == "closed"
    assert r.json()["balance"] == "0.00"
