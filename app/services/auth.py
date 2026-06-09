from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import User
from app.schemas.auth import (
    AuthResponse,
    ClassroomContext,
    FacilityContext,
    LoginMethod,
    UserContext,
)

MOCK_TOKEN_PREFIX = "mock-token:user:"


def verify_password(password: str, password_hash: str) -> bool:
    """해커톤 데모용 비밀번호 검증.

    실제 배포 인증에서는 bcrypt/argon2 기반 hash 검증으로 교체해야 한다.
    """
    if password_hash.startswith("plain:"):
        return password == password_hash.removeprefix("plain:")

    # BE-05 seed의 임시 값과도 호환되게 둔다.
    return password_hash == "test-password-hash" and password == "test-password"


def create_mock_access_token(user_id: int) -> str:
    return f"{MOCK_TOKEN_PREFIX}{user_id}"


def parse_mock_access_token(authorization: str | None) -> int | None:
    if authorization is None:
        return None

    token = authorization.removeprefix("Bearer ").strip()
    if not token.startswith(MOCK_TOKEN_PREFIX):
        return None

    raw_user_id = token.removeprefix(MOCK_TOKEN_PREFIX)
    return int(raw_user_id) if raw_user_id.isdigit() else None


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(
        select(User)
        .options(
            selectinload(User.facility),
            selectinload(User.classroom),
        )
        .where(User.email == email)
    )


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.scalar(
        select(User)
        .options(
            selectinload(User.facility),
            selectinload(User.classroom),
        )
        .where(User.id == user_id)
    )


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def build_user_context(user: User) -> UserContext:
    return UserContext(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        facility=FacilityContext(
            id=user.facility.id,
            name=user.facility.name,
            facility_type=user.facility.facility_type,
        ),
        classroom=(
            ClassroomContext(
                id=user.classroom.id,
                name=user.classroom.name,
                age_group=user.classroom.age_group,
            )
            if user.classroom is not None
            else None
        ),
    )


def build_auth_response(user: User, login_method: LoginMethod) -> AuthResponse:
    return AuthResponse(
        access_token=create_mock_access_token(user.id),
        login_method=login_method,
        user=build_user_context(user),
    )
