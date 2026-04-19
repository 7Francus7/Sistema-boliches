"""E2E del flujo offline-first completo.

Simula el ciclo de vida real del PWA:
  1) Cajero loguea y registra device.
  2) Bootstrap descarga catálogo.
  3) Se 'apaga' la red: se acumulan ventas en la outbox local (lista Python).
  4) Vuelve la red: drenamos la outbox con /sync/batch (incluso con reintentos).
  5) Admin consulta dashboard → ve todo.
  6) Si el cliente reintenta por error de red, los duplicados son idempotentes.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from tests.conftest import auth_headers, login


def test_full_night_offline_then_online(seeded):
    client, data = seeded

    # --- paso 1: login cajero + registro device
    cashier_tok = login(client, data["cashier_email"])["access_token"]
    dev_id = client.post(
        "/devices/register",
        json={"label": "Barra Central", "type": "pos"},
        headers=auth_headers(cashier_tok),
    ).json()["id"]

    # --- paso 2: bootstrap (simula pre-carga del PWA)
    boot = client.get("/bootstrap", headers=auth_headers(cashier_tok)).json()
    stock_inicial = boot["products"][0]["qty_on_hand"]
    assert stock_inicial == 50

    # --- paso 3: red caída → acumular ventas localmente.
    # En el PWA real, Dexie las guarda; acá las acumulamos en una lista.
    outbox = []
    for i in range(10):
        outbox.append(
            {
                "kind": "sale",
                "client_uuid": str(uuid.uuid4()),
                "event_id": data["event_id"],
                "device_id": dev_id,
                "total": "8000",
                "payment_method": "cash",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "items": [
                    {"product_id": data["product_id"], "qty": 1, "unit_price": "8000", "discount": "0"}
                ],
            }
        )

    # Mezclamos un escaneo de QR en medio (puerta también estaba offline).
    door_dev = client.post(
        "/devices/register",
        json={"label": "Puerta", "type": "door"},
        headers=auth_headers(cashier_tok),
    ).json()["id"]
    outbox.append(
        {
            "kind": "access",
            "client_uuid": str(uuid.uuid4()),
            "ticket_id": data["tickets"][0]["id"],
            "event_id": data["event_id"],
            "device_id": door_dev,
            "direction": "in",
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    # --- paso 4: vuelve la red → drain en 2 batches (como haría el loop).
    batch1 = outbox[:7]
    batch2 = outbox[7:]

    r1 = client.post(
        "/sync/batch",
        json={"device_id": dev_id, "ops": batch1},
        headers=auth_headers(cashier_tok),
    )
    r2 = client.post(
        "/sync/batch",
        json={"device_id": dev_id, "ops": batch2},
        headers=auth_headers(cashier_tok),
    )
    assert r1.status_code == 200 and r2.status_code == 200
    statuses = [x["status"] for x in r1.json()["results"] + r2.json()["results"]]
    assert statuses.count("accepted") == 11  # 10 ventas + 1 acceso

    # --- paso 5: el cliente cree que falló el batch 1 y lo reintenta: deben ser duplicates.
    r1_retry = client.post(
        "/sync/batch",
        json={"device_id": dev_id, "ops": batch1},
        headers=auth_headers(cashier_tok),
    )
    assert all(x["status"] == "duplicate" for x in r1_retry.json()["results"])

    # --- paso 6: admin ve el resultado.
    admin_tok = login(client, data["admin_email"])["access_token"]
    dash = client.get("/analytics/dashboard", headers=auth_headers(admin_tok)).json()
    assert dash["sales_count"] == 10
    assert dash["revenue_total"] == 80000.0

    products = client.get("/products", headers=auth_headers(admin_tok)).json()
    # 50 - 10 = 40
    assert products[0]["qty_on_hand"] == 40
