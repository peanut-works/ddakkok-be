from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.product import Product
from app.models.user import User
from app.schemas.product import ProductCreateRequest, ProductResponse
from app.services.auth import get_user_by_id, parse_mock_access_token

router = APIRouter(prefix="/api/products", tags=["products"])


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
    normalized_ingredients = payload.normalized_ingredients or ingredients

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