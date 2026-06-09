from app.models import Classroom, Facility, User
from app.services.auth import (
    build_auth_response,
    create_mock_access_token,
    parse_mock_access_token,
    verify_password,
)


def test_verify_plain_demo_password() -> None:
    assert verify_password("ddakkok1234", "plain:ddakkok1234")
    assert not verify_password("wrong", "plain:ddakkok1234")


def test_parse_mock_access_token() -> None:
    token = create_mock_access_token(1)

    assert token == "mock-token:user:1"
    assert parse_mock_access_token(f"Bearer {token}") == 1
    assert parse_mock_access_token("Bearer invalid-token") is None


def test_build_auth_response_contains_facility_and_classroom_context() -> None:
    facility = Facility(id=1, name="땅콩어린이집", facility_type="DAYCARE")
    classroom = Classroom(id=1, facility_id=1, name="햇님반", age_group="만 3세")
    user = User(
        id=1,
        facility_id=1,
        classroom_id=1,
        email="teacher@ddakkok.com",
        password_hash="plain:ddakkok1234",
        name="김하늘",
        role="TEACHER",
    )
    user.facility = facility
    user.classroom = classroom

    response = build_auth_response(user, "FACILITY")

    assert response.login_method == "FACILITY"
    assert response.user.name == "김하늘"
    assert response.user.facility.name == "땅콩어린이집"
    assert response.user.classroom is not None
    assert response.user.classroom.name == "햇님반"
