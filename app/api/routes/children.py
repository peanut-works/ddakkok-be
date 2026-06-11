from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models.child import Child
from app.models.user import User
from app.schemas.child import ChildDetailResponse
from app.services.auth import get_user_by_id, parse_mock_access_token

router = APIRouter(prefix="/api", tags=["children"])


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
    "/children/{child_id}",
    response_model=ChildDetailResponse,
    summary="아동 상세 정보 조회",
)
def get_child_detail(
    child_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ChildDetailResponse:
    child = db.scalar(
        select(Child)
        .options(selectinload(Child.health_profile))
        .where(
            Child.id == child_id,
            Child.facility_id == current_user.facility_id,
            Child.is_active.is_(True),
        )
    )

    if child is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Child not found",
        )

    return child
