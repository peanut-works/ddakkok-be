import importlib
import sys

from fastapi.testclient import TestClient

sys.modules.pop("app.core.database", None)
sys.modules.pop("app.api.routes.recalls", None)
sys.modules.pop("main", None)
database = importlib.import_module("app.core.database")
SessionLocal = database.SessionLocal

app = importlib.import_module("main").app

client = TestClient(app)

AUTH = {"Authorization": "Bearer mock-token:user:1"}


def test_list_recalls_success():
    response = client.get("/api/recalls", headers=AUTH)

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)
    assert len(data) >= 3

    first = data[0]
    for field in (
        "id",
        "product_name",
        "category",
        "recall_date",
        "reason",
        "source",
    ):
        assert field in first


def test_list_recalls_ordered_by_recall_date_desc():
    response = client.get("/api/recalls", headers=AUTH)

    assert response.status_code == 200

    dates = [item["recall_date"] for item in response.json()]

    assert dates == sorted(dates, reverse=True)


def test_list_recalls_category_filter():
    response = client.get("/api/recalls?category=식품", headers=AUTH)

    assert response.status_code == 200

    data = response.json()

    assert len(data) > 0
    assert all(item["category"] == "식품" for item in data)


def test_list_recalls_keyword_search():
    response = client.get("/api/recalls?q=낮잠패드", headers=AUTH)

    assert response.status_code == 200

    data = response.json()

    assert len(data) > 0
    assert all("낮잠패드" in item["product_name"] for item in data)


def test_list_recalls_limit():
    response = client.get("/api/recalls?limit=1", headers=AUTH)

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_list_recalls_without_token():
    response = client.get("/api/recalls")

    assert response.status_code == 401


def test_get_recall_detail_success():
    response = client.get("/api/recalls/1", headers=AUTH)

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == 1
    assert "product_name" in data
    assert "reason" in data


def test_get_recall_not_found():
    response = client.get("/api/recalls/999999", headers=AUTH)

    assert response.status_code == 404


def test_get_recall_without_token():
    response = client.get("/api/recalls/1")

    assert response.status_code == 401
