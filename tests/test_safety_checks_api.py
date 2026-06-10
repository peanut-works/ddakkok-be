import importlib
import sys

from fastapi.testclient import TestClient
from sqlalchemy import select

sys.modules.pop("app.core.database", None)
database = importlib.import_module("app.core.database")
SessionLocal = database.SessionLocal

safety_check_models = importlib.import_module("app.models.safety_check")
SafetyCheck = safety_check_models.SafetyCheck
SafetyCheckResult = safety_check_models.SafetyCheckResult

app = importlib.import_module("main").app

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


def test_create_safety_check_deduplicates_matched_rules():
    response = client.post(
        "/api/safety-checks",
        headers={"Authorization": "Bearer mock-token:user:1"},
        json={
            "product_id": 102,
            "classroom_id": 1,
            "child_ids": [1, 2],
        },
    )

    assert response.status_code == 201

    data = response.json()

    for result in data["results"]:
        keys = [
            (
                rule["rule_code"],
                rule["status"],
                rule["matched_ingredient"],
                rule["reason"],
            )
            for rule in result["matched_rules"]
        ]

        assert len(keys) == len(set(keys))


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


def test_get_safety_check_detail_success():
    create_response = client.post(
        "/api/safety-checks",
        headers={"Authorization": "Bearer mock-token:user:1"},
        json={
            "product_id": 102,
            "classroom_id": 1,
            "child_ids": [1, 3],
        },
    )

    assert create_response.status_code == 201

    check_id = create_response.json()["id"]

    response = client.get(
        f"/api/safety-checks/{check_id}",
        headers={"Authorization": "Bearer mock-token:user:1"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == check_id
    assert data["product"]["id"] == 102
    assert data["product"]["name"]
    assert data["classroom_id"] == 1

    assert "summary" in data
    assert data["summary"]["overall_status"]
    assert data["summary"]["total_count"] == 2

    assert isinstance(data["results"], list)
    assert len(data["results"]) == 2

    first_result = data["results"][0]

    assert "child_id" in first_result
    assert "child_name" in first_result
    assert "status" in first_result
    assert "matched_ingredient" in first_result
    assert "reason" in first_result
    assert "explanation" in first_result

    assert "overall_explanation" in data


def test_get_safety_check_detail_without_token():
    response = client.get("/api/safety-checks/1")

    assert response.status_code == 401


def test_get_safety_check_detail_with_invalid_token():
    response = client.get(
        "/api/safety-checks/1",
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert response.status_code == 401


def test_get_safety_check_detail_not_found():
    response = client.get(
        "/api/safety-checks/9999",
        headers={"Authorization": "Bearer mock-token:user:1"},
    )

    assert response.status_code == 404


def test_generate_safety_check_explanations_success():
    create_response = client.post(
        "/api/safety-checks",
        headers={"Authorization": "Bearer mock-token:user:1"},
        json={
            "product_id": 102,
            "classroom_id": 1,
            "child_ids": [1, 3],
        },
    )

    assert create_response.status_code == 201

    check_id = create_response.json()["id"]

    response = client.post(
        f"/api/safety-checks/{check_id}/explanations",
        headers={"Authorization": "Bearer mock-token:user:1"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == check_id
    assert "overall_explanation" in data
    assert data["overall_explanation"]

    assert isinstance(data["results"], list)
    assert len(data["results"]) == 2

    for result in data["results"]:
        assert result["explanation"]


def test_generate_safety_check_explanations_without_token():
    response = client.post("/api/safety-checks/1/explanations")

    assert response.status_code == 401


def test_generate_safety_check_explanations_not_found():
    response = client.post(
        "/api/safety-checks/9999/explanations",
        headers={"Authorization": "Bearer mock-token:user:1"},
    )

    assert response.status_code == 404


def test_generate_safety_check_explanations_is_idempotent():
    create_response = client.post(
        "/api/safety-checks",
        headers={"Authorization": "Bearer mock-token:user:1"},
        json={
            "product_id": 102,
            "classroom_id": 1,
            "child_ids": [1, 3],
        },
    )

    assert create_response.status_code == 201

    check_id = create_response.json()["id"]

    db = SessionLocal()

    try:
        before_count = db.scalars(
            select(SafetyCheckResult).where(
                SafetyCheckResult.safety_check_id == check_id
            )
        ).all()
    finally:
        db.close()

    first_response = client.post(
        f"/api/safety-checks/{check_id}/explanations",
        headers={"Authorization": "Bearer mock-token:user:1"},
    )
    second_response = client.post(
        f"/api/safety-checks/{check_id}/explanations",
        headers={"Authorization": "Bearer mock-token:user:1"},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    db = SessionLocal()

    try:
        after_results = db.scalars(
            select(SafetyCheckResult)
            .where(SafetyCheckResult.safety_check_id == check_id)
            .order_by(SafetyCheckResult.id.asc())
        ).all()

        assert len(after_results) == len(before_count)

        for result in after_results:
            assert result.explanation
    finally:
        db.close()
