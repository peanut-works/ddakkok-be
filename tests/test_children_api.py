from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_list_children_by_classroom_success():
    response = client.get(
        "/api/classrooms/1/children",
        headers={"Authorization": "Bearer mock-token:user:1"},
    )

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)
    assert len(data) > 0

    first_child = data[0]

    assert "id" in first_child
    assert "facility_id" in first_child
    assert "classroom_id" in first_child
    assert "name" in first_child
    assert "birth_date" in first_child
    assert "gender" in first_child
    assert "memo" in first_child
    assert "is_active" in first_child

    assert first_child["facility_id"] == 1
    assert first_child["classroom_id"] == 1


def test_get_classroom_children_summary_success():
    response = client.get(
        "/api/classrooms/1/children/summary",
        headers={"Authorization": "Bearer mock-token:user:1"},
    )

    assert response.status_code == 200

    data = response.json()

    assert "classroom" in data
    assert "total_count" in data
    assert "children" in data

    assert data["classroom"]["id"] == 1
    assert data["classroom"]["facility_id"] == 1
    assert data["total_count"] > 0
    assert len(data["children"]) == data["total_count"]

    first_child = data["children"][0]

    assert "id" in first_child
    assert "facility_id" in first_child
    assert "classroom_id" in first_child
    assert "name" in first_child
    assert "birth_date" in first_child
    assert "gender" in first_child
    assert "memo" in first_child
    assert "is_active" in first_child


def test_list_children_by_classroom_without_token():
    response = client.get("/api/classrooms/1/children")

    assert response.status_code == 401


def test_list_children_by_classroom_with_invalid_token():
    response = client.get(
        "/api/classrooms/1/children",
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert response.status_code == 401


def test_list_children_by_not_found_classroom():
    response = client.get(
        "/api/classrooms/9999/children",
        headers={"Authorization": "Bearer mock-token:user:1"},
    )

    assert response.status_code == 404


def test_get_child_detail_success():
    response = client.get(
        "/api/children/1",
        headers={"Authorization": "Bearer mock-token:user:1"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == 1
    assert data["facility_id"] == 1
    assert data["classroom_id"] == 1
    assert "name" in data
    assert "health_profile" in data

    health_profile = data["health_profile"]

    assert health_profile is not None
    assert "allergies" in health_profile
    assert "skin_conditions" in health_profile
    assert "sensitive_ingredients" in health_profile
    assert "notes" in health_profile


def test_get_child_detail_without_token():
    response = client.get("/api/children/1")

    assert response.status_code == 401


def test_get_child_detail_with_invalid_token():
    response = client.get(
        "/api/children/1",
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert response.status_code == 401


def test_get_child_detail_not_found():
    response = client.get(
        "/api/children/9999",
        headers={"Authorization": "Bearer mock-token:user:1"},
    )

    assert response.status_code == 404
