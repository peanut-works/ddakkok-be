from collections.abc import Generator
from types import SimpleNamespace

from fastapi.testclient import TestClient

import main
from app.api.routes import products as products_route

client = TestClient(main.app)


def override_get_db() -> Generator[None, None, None]:
    yield None


def override_get_current_user() -> SimpleNamespace:
    return SimpleNamespace(id=1, facility_id=1)


def test_get_product_by_barcode_success(monkeypatch) -> None:
    def fake_lookup(db: object, *, facility_id: int, barcode: str) -> SimpleNamespace:
        assert facility_id == 1
        assert barcode == "880100000101"
        assert db is None
        return SimpleNamespace(
            id=101,
            facility_id=1,
            name="테스트 물티슈",
            category="WET_TISSUE",
            manufacturer="테스트제조사",
            barcode="880100000101",
            expiry_date=None,
            raw_ingredients_text=None,
            ingredients=["정제수"],
            normalized_ingredients=["정제수"],
            image_url=None,
            ocr_raw_text=None,
            created_by_id=1,
        )

    main.app.dependency_overrides[products_route.get_db] = override_get_db
    main.app.dependency_overrides[products_route.get_current_user] = override_get_current_user
    monkeypatch.setattr(products_route, "get_product_by_barcode", fake_lookup)

    response = client.get("/api/products/barcode/880100000101")

    main.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["id"] == 101
    assert response.json()["barcode"] == "880100000101"


def test_get_product_by_barcode_not_found(monkeypatch) -> None:
    def fake_lookup(db: object, *, facility_id: int, barcode: str) -> SimpleNamespace:
        raise products_route.ProductByBarcodeNotFoundError("Product not found")

    main.app.dependency_overrides[products_route.get_db] = override_get_db
    main.app.dependency_overrides[products_route.get_current_user] = override_get_current_user
    monkeypatch.setattr(products_route, "get_product_by_barcode", fake_lookup)

    response = client.get("/api/products/barcode/880100000199")

    main.app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Product not found"
