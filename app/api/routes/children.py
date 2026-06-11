from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.schemas.child import (
    ChildDetailResponse,
    ChildListItemResponse,
    ClassroomChildrenResponse,
)
from app.services.auth import get_user_by_id, parse_mock_access_token
from app.services.children import (
    ChildNotFoundError,
    ClassroomNotFoundError,
    get_classroom_children,
)
from app.services.children import get_child_detail as get_child_detail_service

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
    "/classrooms/{classroom_id}/children",
    response_model=list[ChildListItemResponse],
    summary="반별 아동 목록 조회",
)
def list_children_by_classroom(
    classroom_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[ChildListItemResponse]:
    try:
        _, children = get_classroom_children(
            db=db,
            current_user=current_user,
            classroom_id=classroom_id,
        )
    except ClassroomNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return children


@router.get(
    "/classrooms/{classroom_id}/children/summary",
    response_model=ClassroomChildrenResponse,
    summary="반별 아동 목록 요약 조회",
)
def get_classroom_children_summary(
    classroom_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ClassroomChildrenResponse:
    try:
        classroom, children = get_classroom_children(
            db=db,
            current_user=current_user,
            classroom_id=classroom_id,
        )
    except ClassroomNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return ClassroomChildrenResponse(
        classroom=classroom,
        total_count=len(children),
        children=children,
    )


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
    try:
        child = get_child_detail_service(
            db=db,
            current_user=current_user,
            child_id=child_id,
        )
    except ChildNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return child
