from decimal import Decimal

from tests.conftest import auth_headers, login


def test_register_device_returns_id(seeded):
    client, data = seeded
    tok = login(client, data["admin_email"])["access_token"]
    r = client.post(
        "/devices/register",
        json={"label": "Admin PC", "type": "admin"},
        headers=auth_headers(tok),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["label"] == "Admin PC"
    assert body["type"] == "admin"
    assert body["id"]


def test_list_devices_scoped_to_venue(seeded):
    client, data = seeded
    tok = login(client, data["admin_email"])["access_token"]
    client.post(
        "/devices/register",
        json={"label": "Barra 1", "type": "pos"},
        headers=auth_headers(tok),
    )
    client.post(
        "/devices/register",
        json={"label": "Puerta 1", "type": "door"},
        headers=auth_headers(tok),
    )
    r = client.get("/devices", headers=auth_headers(tok))
    assert len(r.json()) == 2


def test_product_crud_and_stock_adjust(seeded):
    client, data = seeded
    tok = login(client, data["admin_email"])["access_token"]

    # create
    r = client.post(
        "/products",
        json={
            "sku": "CZ-PINT",
            "name": "Cerveza Pinta",
            "category": "barra",
            "sale_price": "3500",
            "cost_price": "1400",
            "initial_stock": 40,
        },
        headers=auth_headers(tok),
    )
    assert r.status_code == 201
    pid = r.json()["id"]
    assert r.json()["qty_on_hand"] == 40

    # list
    r = client.get("/products", headers=auth_headers(tok))
    assert any(p["sku"] == "CZ-PINT" for p in r.json())

    # adjust stock
    r = client.post(
        f"/products/{pid}/stock",
        json={"qty_delta": 10, "reason": "ingreso"},
        headers=auth_headers(tok),
    )
    assert r.json()["qty_on_hand"] == 50

    r = client.post(
        f"/products/{pid}/stock",
        json={"qty_delta": -5, "reason": "merma"},
        headers=auth_headers(tok),
    )
    assert r.json()["qty_on_hand"] == 45


def test_cashier_cannot_create_products(seeded):
    client, data = seeded
    tok = login(client, data["cashier_email"])["access_token"]
    r = client.post(
        "/products",
        json={"sku": "X", "name": "x", "sale_price": "1"},
        headers=auth_headers(tok),
    )
    assert r.status_code == 403
