from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.schemas.dashboard import DashboardSummaryResponse
from app.services.auth import get_user_by_id, parse_mock_access_token
from app.services.dashboard_service import get_dashboard_summary

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> User:
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

    return user


@router.get(
    "/summary",
    response_model=DashboardSummaryResponse,
    summary="홈 대시보드 요약 조회",
)
def dashboard_summary(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    classroom_id: int | None = None,
) -> DashboardSummaryResponse:
    return get_dashboard_summary(
        db=db,
        current_user=current_user,
        classroom_id=classroom_id,
    )
