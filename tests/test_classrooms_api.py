from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_list_classrooms_success():
    response = client.get(
        "/api/classrooms",
        headers={"Authorization": "Bearer mock-token:user:1"},
    )

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)
    assert len(data) == 2

    first_classroom = data[0]

    assert "id" in first_classroom
    assert "facility_id" in first_classroom
    assert "name" in first_classroom
    assert "age_group" in first_classroom

    assert first_classroom["facility_id"] == 1


def test_list_classrooms_without_token():
    response = client.get("/api/classrooms")

    assert response.status_code == 401


def test_list_classrooms_with_invalid_token():
    response = client.get(
        "/api/classrooms",
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert response.status_code == 401