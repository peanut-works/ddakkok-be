from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.ai.embedding import EmbeddingProvider, get_embedding_provider
from app.ai.factory import get_ai_provider
from app.ai.knowledge_loader import KnowledgeLoader
from app.core.database import get_db
from app.models.user import User
from app.schemas.safety_check import (
    SafetyCheckCreateRequest,
    SafetyCheckDetailResponse,
    SafetyCheckResponse,
)
from app.services.auth import get_user_by_id, parse_mock_access_token
from app.services.safety_checker import (
    SafetyCheckNotFoundError,
    SafetyCheckValidationError,
    generate_safety_check_explanations,
    get_safety_check_detail,
    run_safety_check,
)

router = APIRouter(prefix="/api/safety-checks", tags=["safety-checks"])


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


@router.post(
    "",
    response_model=SafetyCheckResponse,
    status_code=status.HTTP_201_CREATED,
    summary="제품 안전 검사 실행",
)
def create_safety_check(
    payload: SafetyCheckCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SafetyCheckResponse:
    try:
        return run_safety_check(
            db=db,
            product_id=payload.product_id,
            classroom_id=payload.classroom_id,
            child_ids=payload.child_ids,
            current_user=current_user,
        )
    except SafetyCheckValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except SafetyCheckNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{check_id}",
    response_model=SafetyCheckDetailResponse,
    summary="저장된 안전 검사 결과 조회",
)
def get_safety_check(
    check_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SafetyCheckDetailResponse:
    try:
        return get_safety_check_detail(
            db=db,
            check_id=check_id,
            current_user=current_user,
        )
    except SafetyCheckNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/{check_id}/explanations",
    response_model=SafetyCheckDetailResponse,
    summary="저장된 안전 검사 결과 설명 생성",
)
async def create_safety_check_explanations(
    check_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Annotated[AIProvider, Depends(get_ai_provider)],
    embed_provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
) -> SafetyCheckDetailResponse:
    try:
        return await generate_safety_check_explanations(
            db=db,
            check_id=check_id,
            current_user=current_user,
            provider=provider,
            knowledge_loader=KnowledgeLoader(db=db, embed_provider=embed_provider),
        )
    except SafetyCheckNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
