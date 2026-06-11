from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import InvalidBarcodeError
from app.models.product import Product
from app.models.user import User
from app.schemas.error import ErrorResponse
from app.schemas.product import ProductCreateRequest, ProductResponse
from app.services.auth import get_user_by_id, parse_mock_access_token
from app.services.ingredient_normalizer import normalize_ingredients
from app.services.product_lookup import get_products

router = APIRouter(prefix="/api/products", tags=["products"])

FILTERED_PRODUCTS_RESPONSE_EXAMPLE = [
    {
        "id": 101,
        "facility_id": 1,
        "name": "키즈 퓨어 물티슈",
        "category": "WET_TISSUE",
        "manufacturer": "샘플케어",
        "barcode": "8808739000207",
        "expiry_date": "2027-03-15",
        "raw_ingredients_text": "정제수, 글리세린, 페녹시에탄올",
        "ingredients": ["정제수", "글리세린", "페녹시에탄올"],
        "normalized_ingredients": ["정제수", "글리세린", "페녹시에탄올"],
        "image_url": None,
        "ocr_raw_text": None,
        "created_by_id": 1,
    }
]

EMPTY_BARCODE_ERROR_EXAMPLE = {
    "error": {
        "code": "BAD_REQUEST",
        "message": "Barcode must not be empty",
        "details": None,
    }
}


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
    responses={
        200: {
            "description": "시설 제품 목록입니다. barcode 쿼리를 함께 보내면 해당 바코드로 필터링합니다.",
            "content": {
                "application/json": {
                    "example": FILTERED_PRODUCTS_RESPONSE_EXAMPLE,
                }
            },
        },
        400: {
            "model": ErrorResponse,
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
            examples=["8808739000207"],
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
