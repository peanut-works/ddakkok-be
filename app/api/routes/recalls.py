from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.recall_notice import RecallNotice
from app.models.user import User
from app.schemas.recall import RecallNoticeResponse
from app.services.auth import get_user_by_id, parse_mock_access_token

router = APIRouter(prefix="/api/recalls", tags=["recalls"])


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


def _visible_recalls_filter(current_user: User):
    """전체 공개(facility_id IS NULL) + 자기 시설 한정 리콜만 노출."""
    return or_(
        RecallNotice.facility_id.is_(None),
        RecallNotice.facility_id == current_user.facility_id,
    )


@router.get(
    "",
    response_model=list[RecallNoticeResponse],
    summary="리콜 정보 목록 조회 (최신순)",
    description=(
        "활성 리콜 정보를 리콜일 최신순으로 조회합니다. "
        "category로 분류 필터, q로 제품명 부분검색이 가능하며, limit은 최대 100개까지 허용합니다."
    ),
)
def list_recalls(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    category: Annotated[str | None, Query(description="분류 필터 (예: 화장품)")] = None,
    q: Annotated[str | None, Query(description="제품명 부분검색")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[RecallNotice]:
    query = (
        select(RecallNotice)
        .where(
            RecallNotice.is_active.is_(True),
            _visible_recalls_filter(current_user),
        )
        .order_by(RecallNotice.recall_date.desc(), RecallNotice.id.desc())
        .offset(offset)
        .limit(limit)
    )

    if category:
        query = query.where(RecallNotice.category == category)

    if q is not None:
        keyword = q.strip()
        if keyword:
            query = query.where(RecallNotice.product_name.ilike(f"%{keyword}%"))

    return list(db.scalars(query).all())


@router.get(
    "/{recall_id}",
    response_model=RecallNoticeResponse,
    summary="리콜 정보 상세 조회",
)
def get_recall(
    recall_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RecallNotice:
    recall = db.scalar(
        select(RecallNotice).where(
            RecallNotice.id == recall_id,
            RecallNotice.is_active.is_(True),
            _visible_recalls_filter(current_user),
        )
    )

    if recall is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recall notice not found",
        )

    return recall
