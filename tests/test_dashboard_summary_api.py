import importlib
import sys

from fastapi.testclient import TestClient

sys.modules.pop("app.core.database", None)

app = importlib.import_module("main").app

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer mock-token:user:1"}


def _create_safety_check(
    *,
    product_id: int = 102,
    classroom_id: int = 1,
    child_ids: list[int] | None = None,
) -> int:
    response = client.post(
        "/api/safety-checks",
        headers=AUTH_HEADERS,
        json={
            "product_id": product_id,
            "classroom_id": classroom_id,
            "child_ids": child_ids or [1, 2],
        },
    )

    assert response.status_code == 201
    return int(response.json()["id"])


def test_get_dashboard_summary_success():
    _create_safety_check()

    response = client.get("/api/dashboard/summary", headers=AUTH_HEADERS)

    assert response.status_code == 200

    data = response.json()

    assert "recall_alerts" in data
    assert "expiry_alerts" in data
    assert "attention_products" in data
    assert isinstance(data["recall_alerts"], list)
    assert isinstance(data["expiry_alerts"], list)
    assert isinstance(data["attention_products"], list)


def test_get_dashboard_summary_without_token():
    response = client.get("/api/dashboard/summary")

    assert response.status_code == 401


def test_dashboard_recall_alerts_are_sorted_by_latest_date():
    response = client.get("/api/dashboard/summary", headers=AUTH_HEADERS)

    assert response.status_code == 200

    recall_alerts = response.json()["recall_alerts"]
    recall_dates = [alert["recall_date"] for alert in recall_alerts]

    assert len(recall_alerts) >= 3
    assert recall_dates == sorted(recall_dates, reverse=True)
    # 시드 데이터 변경에 결합되지 않도록 특정 제품명 대신 정렬 속성으로 검증
    assert recall_alerts[0]["recall_date"] == max(recall_dates)
    assert recall_alerts[0]["product_name"]
    assert recall_alerts[0]["reason"]


def test_dashboard_expiry_alerts_include_expired_or_expiring_products():
    response = client.get("/api/dashboard/summary", headers=AUTH_HEADERS)

    assert response.status_code == 200

    expiry_alerts = response.json()["expiry_alerts"]
    product_ids = {alert["product_id"] for alert in expiry_alerts}

    assert 108 in product_ids

    expired_alert = next(alert for alert in expiry_alerts if alert["product_id"] == 108)
    assert expired_alert["alert_type"] == "EXPIRED"
    assert expired_alert["severity"] == "HIGH"


def test_dashboard_attention_products_include_recent_non_pass_check():
    check_id = _create_safety_check()

    response = client.get("/api/dashboard/summary", headers=AUTH_HEADERS)

    assert response.status_code == 200

    attention_products = response.json()["attention_products"]
    target = next(
        item for item in attention_products if item["check_id"] == check_id
    )

    assert target["product_id"] == 102
    assert target["overall_status"] == "FAIL"
    assert target["status_label"] == "사용 보류"
    assert "사용 보류" in target["summary"]


def test_dashboard_attention_children_include_only_non_pass_results():
    _create_safety_check(child_ids=[1, 2, 3])

    response = client.get("/api/dashboard/summary", headers=AUTH_HEADERS)

    assert response.status_code == 200

    target = next(
        item for item in response.json()["attention_products"]
        if item["product_id"] == 102
    )
    child_statuses = {child["child_id"]: child["status"] for child in target["children"]}

    assert child_statuses == {
        1: "FAIL",
        2: "WARN",
    }
    assert 3 not in child_statuses


def test_dashboard_attention_products_filter_by_classroom_id():
    class1_check_id = _create_safety_check(
        product_id=102,
        classroom_id=1,
        child_ids=[1, 2],
    )
    class2_check_id = _create_safety_check(
        product_id=105,
        classroom_id=2,
        child_ids=[6, 8],
    )

    response = client.get(
        "/api/dashboard/summary",
        headers=AUTH_HEADERS,
        params={"classroom_id": 2},
    )

    assert response.status_code == 200

    check_ids = {
        item["check_id"]
        for item in response.json()["attention_products"]
    }

    assert class2_check_id in check_ids
    assert class1_check_id not in check_ids
