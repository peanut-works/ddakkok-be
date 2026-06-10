from fastapi.testclient import TestClient

from main import app

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.safety_check import SafetyCheck, SafetyCheckResult

client = TestClient(app)


def test_create_safety_check_success():
    response = client.post(
        "/api/safety-checks",
        headers={"Authorization": "Bearer mock-token:user:1"},
        json={
            "product_id": 102,
            "classroom_id": 1,
            "child_ids": [1, 3],
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["product_id"] == 102
    assert data["classroom_id"] == 1
    assert data["product_name"]
    assert "overall_status" in data
    assert "pass_count" in data
    assert "warn_count" in data
    assert "fail_count" in data
    assert "expired_count" in data
    assert "unknown_count" in data

    assert isinstance(data["results"], list)
    assert len(data["results"]) == 2

    first_result = data["results"][0]

    assert "child_id" in first_result
    assert "child_name" in first_result
    assert "status" in first_result
    assert "matched_rules" in first_result
    assert "reason" in first_result


def test_create_safety_check_only_selected_children():
    response = client.post(
        "/api/safety-checks",
        headers={"Authorization": "Bearer mock-token:user:1"},
        json={
            "product_id": 102,
            "classroom_id": 1,
            "child_ids": [1],
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert len(data["results"]) == 1
    assert data["results"][0]["child_id"] == 1


def test_create_safety_check_without_token():
    response = client.post(
        "/api/safety-checks",
        json={
            "product_id": 102,
            "classroom_id": 1,
            "child_ids": [1],
        },
    )

    assert response.status_code == 401


def test_create_safety_check_with_invalid_token():
    response = client.post(
        "/api/safety-checks",
        headers={"Authorization": "Bearer wrong-token"},
        json={
            "product_id": 102,
            "classroom_id": 1,
            "child_ids": [1],
        },
    )

    assert response.status_code == 401


def test_create_safety_check_with_not_found_product():
    response = client.post(
        "/api/safety-checks",
        headers={"Authorization": "Bearer mock-token:user:1"},
        json={
            "product_id": 9999,
            "classroom_id": 1,
            "child_ids": [1],
        },
    )

    assert response.status_code == 404


def test_create_safety_check_with_not_found_classroom():
    response = client.post(
        "/api/safety-checks",
        headers={"Authorization": "Bearer mock-token:user:1"},
        json={
            "product_id": 102,
            "classroom_id": 9999,
            "child_ids": [1],
        },
    )

    assert response.status_code == 404


def test_create_safety_check_with_not_found_child():
    response = client.post(
        "/api/safety-checks",
        headers={"Authorization": "Bearer mock-token:user:1"},
        json={
            "product_id": 102,
            "classroom_id": 1,
            "child_ids": [9999],
        },
    )

    assert response.status_code == 404


def test_create_safety_check_with_empty_child_ids():
    response = client.post(
        "/api/safety-checks",
        headers={"Authorization": "Bearer mock-token:user:1"},
        json={
            "product_id": 102,
            "classroom_id": 1,
            "child_ids": [],
        },
    )

    assert response.status_code == 422


def test_create_safety_check_with_duplicate_child_ids():
    response = client.post(
        "/api/safety-checks",
        headers={"Authorization": "Bearer mock-token:user:1"},
        json={
            "product_id": 102,
            "classroom_id": 1,
            "child_ids": [1, 1],
        },
    )

    assert response.status_code == 400


def test_create_safety_check_saves_result_to_database():
    response = client.post(
        "/api/safety-checks",
        headers={"Authorization": "Bearer mock-token:user:1"},
        json={
            "product_id": 102,
            "classroom_id": 1,
            "child_ids": [1, 3],
        },
    )

    assert response.status_code == 201

    data = response.json()
    safety_check_id = data["id"]

    db = SessionLocal()

    try:
        safety_check = db.get(SafetyCheck, safety_check_id)

        assert safety_check is not None
        assert safety_check.product_id == 102
        assert safety_check.classroom_id == 1
        assert safety_check.overall_status == data["overall_status"]
        assert safety_check.pass_count == data["pass_count"]
        assert safety_check.warn_count == data["warn_count"]
        assert safety_check.fail_count == data["fail_count"]
        assert safety_check.expired_count == data["expired_count"]
        assert safety_check.unknown_count == data["unknown_count"]

        results = db.scalars(
            select(SafetyCheckResult)
            .where(SafetyCheckResult.safety_check_id == safety_check_id)
            .order_by(SafetyCheckResult.child_id.asc())
        ).all()

        assert len(results) == 2

        child_ids = [result.child_id for result in results]
        assert child_ids == [1, 3]

        for result in results:
            assert result.status in ["PASS", "WARN", "FAIL", "EXPIRED", "UNKNOWN"]
            assert result.reason is not None

        fail_result = next(
            result for result in results if result.status == "FAIL"
        )

        assert fail_result.matched_ingredient is not None
        assert fail_result.reason is not None

    finally:
        db.close()