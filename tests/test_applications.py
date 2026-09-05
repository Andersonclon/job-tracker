import pytest


@pytest.fixture
def application(client, platform_id):
    resp = client.post(
        "/applications",
        json={
            "platform_id": platform_id,
            "company": "Ozon",
            "position": "Python-разработчик",
            "url": "https://hh.ru/vacancy/1",
        },
    )
    assert resp.status_code == 201
    return resp.json()


def test_create_application_starts_as_sent(application):
    assert application["status"] == "sent"
    assert application["sent_at"]
    assert len(application["events"]) == 1


def test_create_application_unknown_platform(client):
    resp = client.post(
        "/applications",
        json={"platform_id": 9999, "company": "X", "position": "Y"},
    )
    assert resp.status_code == 404


def test_get_application(client, application):
    resp = client.get(f"/applications/{application['id']}")
    assert resp.status_code == 200
    assert resp.json()["company"] == "Ozon"


def test_get_missing_application(client):
    assert client.get("/applications/424242").status_code == 404


def test_status_change_writes_event(client, application):
    resp = client.post(
        f"/applications/{application['id']}/status",
        json={"status": "invited", "comment": "Позвали на скрининг"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "invited"
    assert [e["status"] for e in body["events"]] == ["sent", "invited"]


def test_patch_application(client, application):
    resp = client.patch(
        f"/applications/{application['id']}", json={"notes": "Просили тестовое"}
    )
    assert resp.status_code == 200
    assert resp.json()["notes"] == "Просили тестовое"


def test_filter_by_status(client, application, platform_id):
    client.post(
        "/applications",
        json={"platform_id": platform_id, "company": "Avito", "position": "Junior Python"},
    )
    client.post(
        f"/applications/{application['id']}/status", json={"status": "rejected"}
    )

    sent = client.get("/applications", params={"status": "sent"}).json()
    rejected = client.get("/applications", params={"status": "rejected"}).json()

    assert [a["company"] for a in sent] == ["Avito"]
    assert [a["company"] for a in rejected] == ["Ozon"]


def test_delete_application(client, application):
    assert client.delete(f"/applications/{application['id']}").status_code == 204
    assert client.get(f"/applications/{application['id']}").status_code == 404
