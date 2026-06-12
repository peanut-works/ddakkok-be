import re
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.ai.factory import get_ai_provider
from app.ai.ner import LabelParser, ProductLabelParseResult
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.exceptions import InvalidBarcodeError
from app.models.product import Product
from app.models.user import User
from app.schemas.product import (
    EMPTY_BARCODE_ERROR_EXAMPLE,
    PRODUCT_LIST_RESPONSE_EXAMPLE,
    ProductCreateRequest,
    ProductLabelTextParseRequest,
    ProductLabelTextParseResponse,
    ProductResponse,
)
from app.services.auth import get_user_by_id, parse_mock_access_token
from app.services.ingredient_normalizer import normalize_ingredients
from app.services.product_lookup import get_products

router = APIRouter(prefix="/api/products", tags=["products"])

_INGREDIENT_STOP_KEYWORDS = (
    "유형:",
    "용량:",
    "품번:",
    "품명:",
    "사용상의 주의사항",
    "주의사항",
    "사용기한",
    "유통기한",
)


def _parse_expiry_date(value: str) -> date | None:
    clean_value = value.strip().replace(".", "-")
    if not clean_value:
        return None

    try:
        return datetime.strptime(clean_value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _normalize_expiry_date(value: str | None) -> date | None:
    if not value:
        return None

    date_match = re.search(r"\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}", value)
    if date_match is None:
        return None

    return _parse_expiry_date(date_match.group(0))


def _extract_line_value(text: str, labels: tuple[str, ...]) -> str | None:
    for label in labels:
        match = re.search(rf"{re.escape(label)}\s*([^\n]+)", text)
        if match:
            value = match.group(1).strip()
            return value or None
    return None


def _extract_product_name(text: str) -> str | None:
    return _extract_line_value(text, ("품명:", "제품명:"))


def _extract_manufacturer(text: str) -> str | None:
    return _extract_line_value(
        text,
        ("화장품책임판매업자:", "화장품제조업자:", "제조사:"),
    )


def _extract_ingredient_text(text: str) -> str | None:
    match = re.search(r"(전성분|성분)\s*:\s*", text)
    if not match:
        return None

    start = match.end()
    end = len(text)

    for keyword in _INGREDIENT_STOP_KEYWORDS:
        keyword_index = text.find(keyword, start)
        if keyword_index != -1:
            end = min(end, keyword_index)

    ingredient_text = text[start:end].strip()
    return ingredient_text or None


def _extract_ingredients(text: str) -> list[str]:
    ingredient_text = _extract_ingredient_text(text)
    if ingredient_text is None:
        return []

    return [
        ingredient.strip()
        for ingredient in ingredient_text.replace("\n", " ").split(",")
        if ingredient.strip()
    ]


def _extract_expiry_date(text: str) -> date | None:
    match = re.search(r"(사용기한|유통기한)[^\n:：]*[:：]?\s*([^\n]+)", text)
    if not match:
        return None

    return _normalize_expiry_date(match.group(2))


def _parse_label_text_with_regex(text: str) -> ProductLabelParseResult:
    ingredient_text = _extract_ingredient_text(text)
    ingredients = _extract_ingredients(text)

    return ProductLabelParseResult(
        name=_extract_product_name(text),
        manufacturer=_extract_manufacturer(text),
        expiry_date=None,
        raw_ingredients_text=ingredient_text,
        ingredients=ingredients,
    )


def _unwrap_primary_provider(provider: AIProvider) -> AIProvider:
    current = provider
    seen_ids: set[int] = set()

    while hasattr(current, "_primary") and id(current) not in seen_ids:
        seen_ids.add(id(current))
        current = current._primary  # type: ignore[attr-defined]

    return current


async def _parse_label_text(
    *,
    text: str,
    provider: AIProvider,
    settings: Settings,
) -> ProductLabelParseResult:
    if not text.strip():
        return ProductLabelParseResult()

    if settings.ai_provider not in {"openai", "gms"}:
        return _parse_label_text_with_regex(text)

    try:
        # FallbackAIProvider는 실패 시 mock_data.py를 반환하므로,
        # 이 엔드포인트에서는 primary provider만 사용하고 실패 시 regex로 복구한다.
        primary_provider = _unwrap_primary_provider(provider)
        return await LabelParser(primary_provider).parse_product_label(text)
    except Exception:
        return _parse_label_text_with_regex(text)


FILTERED_PRODUCTS_RESPONSE_EXAMPLE = [
    {
        "id": 101,
        "facility_id": 1,
        "name": "세이프 데일리 핸드워시",
        "category": "CLEANSER",
        "manufacturer": "해커톤생활건강",
        "barcode": "880100000101",
        "expiry_date": "2027-12-31",
        "raw_ingredients_text": "정제수, 글리세린, 코코베타인, 구연산",
        "ingredients": ["정제수", "글리세린", "코코베타인", "구연산"],
        "normalized_ingredients": ["정제수", "글리세린", "코코베타인", "구연산"],
        "image_url": None,
        "ocr_raw_text": None,
        "created_by_id": 1,
    }
]


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
    "",
    response_model=list[ProductResponse],
    summary="제품 목록 조회",
    description=(
        "로그인 사용자의 시설 기준 제품 목록을 조회합니다. "
        "barcode query parameter를 보내면 해당 바코드 제품만 필터링합니다. "
    ),
    responses={
        200: {
            "description": "시설 제품 목록입니다. barcode 쿼리를 함께 보내면 해당 바코드로 필터링합니다.",
            "content": {
                "application/json": {
                    "example": PRODUCT_LIST_RESPONSE_EXAMPLE,
                }
            },
        },
        400: {
            "description": "barcode 쿼리에서 공백을 제거한 뒤 빈 값이 된 경우",
            "content": {
                "application/json": {
                    "example": EMPTY_BARCODE_ERROR_EXAMPLE,
                }
            },
        },
    },
)
def list_products(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    barcode: Annotated[
        str | None,
        Query(
            description="제품 조회용 바코드 필터",
            examples=["880100000101"],
        ),
    ] = None,
) -> list[ProductResponse]:
    try:
        return get_products(
            db,
            facility_id=current_user.facility_id,
            barcode=barcode,
        )
    except InvalidBarcodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Barcode must not be empty",
        ) from exc


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    summary="제품 상세 조회",
)
def get_product(
    product_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProductResponse:
    product = db.scalar(
        select(Product).where(
            Product.id == product_id,
            Product.facility_id == current_user.facility_id,
        )
    )

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    return product


@router.post(
    "/parse-label-text",
    response_model=ProductLabelTextParseResponse,
    summary="제품 라벨 텍스트 파싱",
)
async def parse_product_label_text(
    payload: ProductLabelTextParseRequest,
    db: Annotated[Session, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    provider: Annotated[AIProvider, Depends(get_ai_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProductLabelTextParseResponse:
    parsed = await _parse_label_text(
        text=payload.text,
        provider=provider,
        settings=settings,
    )
    ingredients = parsed.ingredients

    return ProductLabelTextParseResponse(
        name=parsed.name,
        category=payload.category,
        manufacturer=parsed.manufacturer,
        expiry_date=_normalize_expiry_date(parsed.expiry_date) or _extract_expiry_date(payload.text),
        raw_ingredients_text=parsed.raw_ingredients_text,
        ingredients=ingredients,
        normalized_ingredients=normalize_ingredients(db, ingredients),
        ocr_raw_text=payload.text,
    )


@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="제품 등록",
)
def create_product(
    payload: ProductCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProductResponse:
    ingredients = payload.ingredients
    normalized_ingredients = normalize_ingredients(db, ingredients)

    product = Product(
        facility_id=current_user.facility_id,
        name=payload.name,
        category=payload.category,
        manufacturer=payload.manufacturer,
        barcode=payload.barcode,
        expiry_date=payload.expiry_date,
        raw_ingredients_text=payload.raw_ingredients_text,
        ingredients=ingredients,
        normalized_ingredients=normalized_ingredients,
        image_url=payload.image_url,
        ocr_raw_text=payload.ocr_raw_text,
        created_by_id=current_user.id,
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    return product
