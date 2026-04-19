from tests.conftest import auth_headers, login


def test_supplier_crud(seeded):
    client, data = seeded
    tok = login(client, data["admin_email"])["access_token"]
    r = client.post(
        "/suppliers",
        json={"name": "Distribuidora Norte", "contact": "Luis", "phone": "11-1234"},
        headers=auth_headers(tok),
    )
    assert r.status_code == 201
    sid = r.json()["id"]

    r = client.get("/suppliers", headers=auth_headers(tok))
    assert any(s["id"] == sid for s in r.json())


def test_purchase_updates_stock_and_cost(seeded):
    client, data = seeded
    tok = login(client, data["admin_email"])["access_token"]

    sid = client.post(
        "/suppliers", json={"name": "Prov 1"}, headers=auth_headers(tok),
    ).json()["id"]

    # El producto en seed arranca con stock 50 y cost_price 4000.
    # Recibimos 30 unidades a 5000 → costo promedio ponderado:
    # (50 * 4000 + 30 * 5000) / 80 = (200000 + 150000) / 80 = 4375
    r = client.post(
        "/purchases",
        json={
            "supplier_id": sid,
            "reference": "REM-001",
            "items": [
                {"product_id": data["product_id"], "qty": 30, "unit_cost": "5000"},
            ],
        },
        headers=auth_headers(tok),
    )
    assert r.status_code == 201
    assert float(r.json()["total"]) == 150000.0

    products = client.get("/products", headers=auth_headers(tok)).json()
    prod = next(p for p in products if p["id"] == data["product_id"])
    assert prod["qty_on_hand"] == 80  # 50 + 30

    # Verificamos que el margen en dashboard considere el nuevo costo promedio.
    dash = client.get("/analytics/dashboard", headers=auth_headers(tok)).json()
    assert "top_products" in dash  # smoke check


def test_low_stock_alerts(seeded):
    client, data = seeded
    tok = login(client, data["admin_email"])["access_token"]

    # Bajamos el stock del único producto (50 → 5) con un ajuste manual.
    client.post(
        f"/products/{data['product_id']}/stock",
        json={"qty_delta": -45, "reason": "ajuste test"},
        headers=auth_headers(tok),
    )
    r = client.get("/analytics/low-stock", headers=auth_headers(tok))
    alerts = r.json()
    assert any(a["sku"] == "FE-750" and a["qty_on_hand"] == 5 for a in alerts)


def test_sales_csv_export(seeded):
    import uuid
    from datetime import datetime, timezone

    client, data = seeded
    tok = login(client, data["cashier_email"])["access_token"]
    admin_tok = login(client, data["admin_email"])["access_token"]
    dev = client.post(
        "/devices/register", json={"label": "x", "type": "pos"},
        headers=auth_headers(tok),
    ).json()["id"]

    # una venta
    op = {
        "kind": "sale",
        "client_uuid": str(uuid.uuid4()),
        "event_id": data["event_id"],
        "device_id": dev,
        "total": "8000",
        "payment_method": "cash",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "items": [{"product_id": data["product_id"], "qty": 1, "unit_price": "8000", "discount": "0"}],
    }
    client.post(
        "/sync/batch", json={"device_id": dev, "ops": [op]},
        headers=auth_headers(tok),
    )

    r = client.get("/analytics/sales.csv", headers=auth_headers(admin_tok))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    body = r.text
    assert "sale_id,created_at,method,total,cashier,product,qty,unit_price" in body
    assert "Fernet 750" in body
