from types import SimpleNamespace

import pytest

from app.services.product_lookup import (
    InvalidBarcodeError,
    ProductByBarcodeNotFoundError,
    get_product_by_barcode,
)


class FakeSession:
    def __init__(self, product: object | None) -> None:
        self.product = product

    def scalar(self, _query: object) -> object | None:
        return self.product


def test_get_product_by_barcode_returns_product() -> None:
    product = SimpleNamespace(id=101, facility_id=1, barcode="880100000101", name="테스트 제품")
    db = FakeSession(product)

    result = get_product_by_barcode(
        db,
        facility_id=1,
        barcode=" 880100000101 ",
    )

    assert result is product


def test_get_product_by_barcode_raises_not_found() -> None:
    db = FakeSession(None)

    with pytest.raises(ProductByBarcodeNotFoundError):
        get_product_by_barcode(
            db,
            facility_id=1,
            barcode="880100000199",
        )


def test_get_product_by_barcode_rejects_blank_input() -> None:
    db = FakeSession(None)

    with pytest.raises(InvalidBarcodeError):
        get_product_by_barcode(
            db,
            facility_id=1,
            barcode="   ",
        )
