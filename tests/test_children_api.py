import importlib
import sys

from fastapi.testclient import TestClient

from app.models.child import Child
from app.models.classroom import Classroom
from app.models.facility import Facility

sys.modules.pop("app.core.database", None)
sys.modules.pop("app.api.routes.children", None)
sys.modules.pop("app.api.routes.classrooms", None)
sys.modules.pop("main", None)
database = importlib.import_module("app.core.database")
SessionLocal = database.SessionLocal

app = importlib.import_module("main").app

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
    assert "health_profile" in first_child

    assert first_child["facility_id"] == 1
    assert first_child["classroom_id"] == 1

    profile_by_child_id = {
        child["id"]: child["health_profile"]
        for child in data
    }

    assert profile_by_child_id[1] is not None
    assert "allergies" in profile_by_child_id[1]
    assert isinstance(profile_by_child_id[1]["allergies"], list)
    assert "우유" in profile_by_child_id[1]["allergies"]
    assert "sensitive_ingredients" in profile_by_child_id[1]
    assert isinstance(profile_by_child_id[1]["sensitive_ingredients"], list)
    assert "notes" in profile_by_child_id[1]


def test_list_children_by_classroom_handles_child_without_health_profile():
    db = SessionLocal()
    child = Child(
        facility_id=1,
        classroom_id=1,
        name="건강프로필없는아동",
        birth_date=None,
        gender=None,
        memo=None,
        is_active=True,
    )

    try:
        db.add(child)
        db.commit()
        db.refresh(child)
        child_id = child.id

        response = client.get(
            "/api/classrooms/1/children",
            headers={"Authorization": "Bearer mock-token:user:1"},
        )

        assert response.status_code == 200

        data = response.json()
        target = next(item for item in data if item["id"] == child_id)

        assert "health_profile" in target
        assert target["health_profile"] is None
    finally:
        db.delete(child)
        db.commit()
        db.close()


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


def test_list_children_by_other_facility_classroom_not_found():
    db = SessionLocal()
    facility = Facility(
        name="다른 시설",
        address="서울시 테스트구",
        phone="02-9999-9999",
    )
    classroom = Classroom(
        facility=facility,
        name="다른 반",
        age_group="만 4세",
    )

    try:
        db.add(facility)
        db.add(classroom)
        db.commit()
        db.refresh(classroom)
        classroom_id = classroom.id

        response = client.get(
            f"/api/classrooms/{classroom_id}/children",
            headers={"Authorization": "Bearer mock-token:user:1"},
        )

        assert response.status_code == 404
    finally:
        db.delete(classroom)
        db.delete(facility)
        db.commit()
        db.close()


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
