"""Кэш и рейт-лимитер на уровне HTTP-ручек."""

from app import crud


def test_second_stats_call_is_served_from_cache(client, platform_id, monkeypatch):
    calls = {"n": 0}
    real = crud.platform_stats

    def counting(db):
        calls["n"] += 1
        return real(db)

    monkeypatch.setattr(crud, "platform_stats", counting)

    assert client.get("/stats").status_code == 200
    assert client.get("/stats").status_code == 200

    assert calls["n"] == 1, "второй /stats должен был прийти из Redis, а не из базы"


def test_creating_application_invalidates_stats_cache(client, platform_id):
    assert client.get("/stats").json() == []

    resp = client.post(
        "/applications",
        json={"platform_id": platform_id, "company": "Ozon", "position": "Python"},
    )
    assert resp.status_code == 201

    assert client.get("/stats").json() == [
        {"platform": "hh.ru", "total": 1, "responded": 0}
    ], "POST заявки обязан сбросить закэшированную статистику"


def test_exceeding_rate_limit_returns_429(client):
    # /stats лимитирован 20 запросами в минуту
    codes = [client.get("/stats").status_code for _ in range(21)]

    assert codes.count(200) == 20
    assert codes[-1] == 429
