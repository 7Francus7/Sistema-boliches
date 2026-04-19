from tests.conftest import auth_headers, login


def test_login_ok(seeded):
    client, data = seeded
    r = login(client, data["admin_email"])
    assert r["role"] == "admin"
    assert r["venue_id"] == data["venue_id"]


def test_login_bad_credentials(seeded):
    client, data = seeded
    r = client.post("/auth/login", json={"email": data["admin_email"], "password": "nope"})
    assert r.status_code == 401


def test_bootstrap_returns_catalog(seeded):
    client, data = seeded
    tok = login(client, data["admin_email"])["access_token"]
    r = client.get("/bootstrap", headers=auth_headers(tok))
    assert r.status_code == 200
    body = r.json()
    assert body["event"]["id"] == data["event_id"]
    assert len(body["products"]) == 1
    assert body["products"][0]["qty_on_hand"] == 50
    assert len(body["tickets"]) == 3


def test_bootstrap_requires_auth(seeded):
    client, _ = seeded
    assert client.get("/bootstrap").status_code == 401
