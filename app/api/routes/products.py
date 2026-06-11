from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.product import Product
from app.models.user import User
from app.schemas.error import ErrorResponse
from app.schemas.product import ProductCreateRequest, ProductResponse
from app.services.auth import get_user_by_id, parse_mock_access_token
from app.services.ingredient_normalizer import normalize_ingredients
from app.services.product_lookup import (
    InvalidBarcodeError,
    ProductByBarcodeNotFoundError,
    get_product_by_barcode,
)

router = APIRouter(prefix="/api/products", tags=["products"])

BARCODE_PRODUCT_RESPONSE_EXAMPLE = {
    "id": 101,
    "facility_id": 1,
    "name": "하기스 퓨어 물티슈",
    "category": "WET_TISSUE",
    "manufacturer": "유한킴벌리",
    "barcode": "880000000101",
    "expiry_date": "2027-03-15",
    "raw_ingredients_text": "정제수, 글리세린, 페녹시에탄올",
    "ingredients": ["정제수", "글리세린", "페녹시에탄올"],
    "normalized_ingredients": ["정제수", "글리세린", "페녹시에탄올"],
    "image_url": None,
    "ocr_raw_text": None,
    "created_by_id": 1,
}

EMPTY_BARCODE_ERROR_EXAMPLE = {
    "error": {
        "code": "BAD_REQUEST",
        "message": "Barcode must not be empty",
        "details": None,
    }
}

PRODUCT_NOT_FOUND_ERROR_EXAMPLE = {
    "error": {
        "code": "NOT_FOUND",
        "message": "Product not found",
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
)
def list_products(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[ProductResponse]:
    products = db.scalars(
        select(Product)
        .where(Product.facility_id == current_user.facility_id)
        .order_by(Product.id.asc())
    ).all()

    return products


@router.get(
    "/barcode/{barcode}",
    response_model=ProductResponse,
    summary="바코드로 제품 조회",
    responses={
        200: {
            "description": "Barcode matched a product in the current facility",
            "content": {
                "application/json": {
                    "example": BARCODE_PRODUCT_RESPONSE_EXAMPLE,
                }
            },
        },
        400: {
            "model": ErrorResponse,
            "description": "Barcode is blank after trimming whitespace",
            "content": {
                "application/json": {
                    "example": EMPTY_BARCODE_ERROR_EXAMPLE,
                }
            },
        },
        404: {
            "model": ErrorResponse,
            "description": "No product with the barcode exists in the current facility",
            "content": {
                "application/json": {
                    "example": PRODUCT_NOT_FOUND_ERROR_EXAMPLE,
                }
            },
        },
    },
)
def get_product_by_barcode_route(
    barcode: Annotated[
        str,
        Path(
            description="Scan result barcode value",
            examples=["880000000101"],
        ),
    ],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProductResponse:
    try:
        return get_product_by_barcode(
            db,
            facility_id=current_user.facility_id,
            barcode=barcode,
        )
    except InvalidBarcodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Barcode must not be empty",
        ) from exc
    except ProductByBarcodeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
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
