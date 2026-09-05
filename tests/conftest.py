import os

# ВАЖНО: подменяем адрес БД до импорта приложения, чтобы тесты
# никогда не постучались в рабочую базу.
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://tracker:tracker@localhost:5432/tracker_test",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def platform_id(client):
    resp = client.post("/platforms", json={"name": "hh.ru", "url": "https://hh.ru"})
    assert resp.status_code == 201
    return resp.json()["id"]
