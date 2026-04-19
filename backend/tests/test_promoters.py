from tests.conftest import auth_headers, login


def test_promoter_crud_and_commission(seeded):
    client, data = seeded
    tok = login(client, data["admin_email"])["access_token"]

    # create
    r = client.post(
        "/promoters",
        json={"name": "Juana La RRPP", "phone": "11-5555", "commission_pct": "15"},
        headers=auth_headers(tok),
    )
    assert r.status_code == 201
    pid = r.json()["id"]
    assert r.json()["slug"] == "juana-la-rrpp"
    assert r.json()["commission_pct"] == "15.00"

    # atribuimos todos los tickets a Juana
    for t in data["tickets"]:
        r2 = client.post(
            f"/promoters/{pid}/attribute-ticket",
            json={"ticket_id": t["id"]},
            headers=auth_headers(tok),
        )
        assert r2.status_code == 200

    # liquidación de comisiones
    comms = client.get("/analytics/commissions", headers=auth_headers(tok)).json()
    assert len(comms) == 1
    c = comms[0]
    # 3 tickets a 5000 = 15000, 15% = 2250
    assert c["tickets_sold"] == 3
    assert c["revenue"] == 15000.0
    assert c["commission_amount"] == 2250.0


def test_slug_collision(seeded):
    client, data = seeded
    tok = login(client, data["admin_email"])["access_token"]
    client.post("/promoters", json={"name": "Tano", "commission_pct": "10"}, headers=auth_headers(tok))
    r = client.post("/promoters", json={"name": "Tano", "commission_pct": "10"}, headers=auth_headers(tok))
    assert r.status_code == 409


def test_cashier_cannot_manage_promoters(seeded):
    client, data = seeded
    tok = login(client, data["cashier_email"])["access_token"]
    r = client.post("/promoters", json={"name": "X", "commission_pct": "1"}, headers=auth_headers(tok))
    assert r.status_code == 403
