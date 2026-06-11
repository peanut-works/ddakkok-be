from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.params import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models.child import Child
from app.models.classroom import Classroom
from app.models.user import User
from app.schemas.child import ChildListItemResponse
from app.schemas.classroom import ClassroomResponse
from app.services.auth import get_user_by_id, parse_mock_access_token

router = APIRouter(prefix="/api/classrooms", tags=["classrooms"])


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


@router.get("", response_model=list[ClassroomResponse])
def list_classrooms(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[ClassroomResponse]:
    classrooms = db.scalars(
        select(Classroom)
        .where(Classroom.facility_id == current_user.facility_id)
        .order_by(Classroom.id.asc())
    ).all()

    return classrooms


@router.get(
    "/{classroom_id}/children",
    response_model=list[ChildListItemResponse],
    summary="반별 아동 목록 조회",
)
def list_children_by_classroom(
    classroom_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[ChildListItemResponse]:
    classroom = db.get(Classroom, classroom_id)

    if classroom is None or classroom.facility_id != current_user.facility_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Classroom not found",
        )

    children = db.scalars(
        select(Child)
        .options(selectinload(Child.health_profile))
        .where(
            Child.classroom_id == classroom_id,
            Child.facility_id == current_user.facility_id,
            Child.is_active.is_(True),
        )
        .order_by(Child.id.asc())
    ).all()

    return children
