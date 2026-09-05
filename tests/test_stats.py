def test_stats_counts_responses(client, platform_id):
    for company in ("Ozon", "Avito", "Yandex"):
        client.post(
            "/applications",
            json={"platform_id": platform_id, "company": company, "position": "Python"},
        )

    first = client.get("/applications").json()[-1]
    client.post(f"/applications/{first['id']}/status", json={"status": "invited"})

    rows = client.get("/stats").json()
    assert rows == [{"platform": "hh.ru", "total": 3, "responded": 1}]


def test_stats_empty(client):
    assert client.get("/stats").json() == []
