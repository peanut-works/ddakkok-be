from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import InvalidBarcodeError
from app.models.product import Product


def get_products(
    db: Session,
    *,
    facility_id: int,
    barcode: str | None = None,
) -> list[Product]:
    """Return facility products, optionally filtered by barcode."""
    query = select(Product).where(Product.facility_id == facility_id)

    if barcode is not None:
        normalized_barcode = barcode.strip()

        if not normalized_barcode:
            raise InvalidBarcodeError("Barcode must not be empty")

        query = query.where(Product.barcode == normalized_barcode)

    return db.scalars(query.order_by(Product.id.asc())).all()
