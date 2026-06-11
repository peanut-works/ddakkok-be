from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product


class ProductLookupError(Exception):
    """Base error for product lookup service."""


class ProductByBarcodeNotFoundError(ProductLookupError):
    """Raised when a product cannot be found by barcode."""


class InvalidBarcodeError(ProductLookupError):
    """Raised when a barcode input is empty after normalization."""


def get_product_by_barcode(
    db: Session,
    *,
    facility_id: int,
    barcode: str,
) -> Product:
    """Look up a product by barcode within the current facility."""
    normalized_barcode = barcode.strip()

    if not normalized_barcode:
        raise InvalidBarcodeError("Barcode must not be empty")

    product = db.scalar(
        select(Product).where(
            Product.facility_id == facility_id,
            Product.barcode == normalized_barcode,
        )
    )

    if product is None:
        raise ProductByBarcodeNotFoundError("Product not found")

    return product
