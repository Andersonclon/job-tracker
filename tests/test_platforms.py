def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_create_platform(client):
    resp = client.post("/platforms", json={"name": "Профи.ру"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "Профи.ру"


def test_duplicate_platform_rejected(client, platform_id):
    resp = client.post("/platforms", json={"name": "hh.ru"})
    assert resp.status_code == 409


def test_list_platforms(client, platform_id):
    resp = client.get("/platforms")
    assert resp.status_code == 200
    assert [p["id"] for p in resp.json()] == [platform_id]
