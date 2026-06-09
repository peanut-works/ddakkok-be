from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.auth import AuthResponse, KakaoLoginRequest, LoginRequest, UserContext
from app.services.auth import (
    authenticate_user,
    build_auth_response,
    build_user_context,
    get_user_by_email,
    get_user_by_id,
    parse_mock_access_token,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

DEMO_EMAIL = "teacher@ddakkok.com"


@router.post("/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> AuthResponse:
    user = authenticate_user(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    return build_auth_response(user, payload.login_method)


@router.post("/demo", response_model=AuthResponse)
def demo_login(db: Annotated[Session, Depends(get_db)]) -> AuthResponse:
    user = get_user_by_email(db, DEMO_EMAIL)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Demo user is not seeded",
        )

    return build_auth_response(user, "DEMO")


@router.get("/me", response_model=UserContext)
def get_me(
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> UserContext:
    user_id = parse_mock_access_token(authorization)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing access token",
        )

    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing access token",
        )

    return build_user_context(user)


@router.post("/kakao", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def kakao_login(payload: KakaoLoginRequest) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Kakao login is pending until OAuth callback server settings are available",
    )
