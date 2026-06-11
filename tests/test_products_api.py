from __future__ import annotations

from collections.abc import Generator
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import main
from app.api.routes import products as products_route
from app.core.exceptions import InvalidBarcodeError
from app.models.product import Product

client = TestClient(main.app)
AUTH_HEADERS = {"Authorization": "Bearer mock-token:user:1"}


class FakeSession:
    def __init__(self) -> None:
        self.scalar_result: object | None = None
        self.added: list[object] = []
        self.committed = False
        self.refreshed = False
        self._next_id = 1000

    def scalar(self, _query: object) -> object | None:
        return self.scalar_result

    def add(self, obj: object) -> None:
        if hasattr(obj, "id") and getattr(obj, "id", None) is None:
            obj.id = self._next_id  # type: ignore[attr-defined]
            self._next_id += 1
        self.added.append(obj)

    def commit(self) -> None:
        self.committed = True

    def refresh(self, _obj: object) -> None:
        self.refreshed = True


def override_get_current_user() -> SimpleNamespace:
    return SimpleNamespace(id=1, facility_id=1)


def install_db_override(db: FakeSession) -> None:
    def override_get_db() -> Generator[FakeSession, None, None]:
        yield db

    main.app.dependency_overrides[products_route.get_db] = override_get_db


def install_authenticated_overrides(db: FakeSession) -> None:
    install_db_override(db)
    main.app.dependency_overrides[products_route.get_current_user] = override_get_current_user


def clear_overrides() -> None:
    main.app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _reset_overrides() -> Generator[None, None, None]:
    yield
    clear_overrides()


def test_list_products_success(monkeypatch) -> None:
    db = FakeSession()
    install_authenticated_overrides(db)

    monkeypatch.setattr(
        products_route,
        "get_products",
        lambda _db, *, facility_id, barcode=None: [
            SimpleNamespace(
                id=101,
                facility_id=facility_id,
                name="Kids Pure Wipes",
                category="WET_TISSUE",
                manufacturer="Sample Care",
                barcode="880100000101",
                expiry_date=None,
                raw_ingredients_text=None,
                ingredients=["purified water"],
                normalized_ingredients=["purified water"],
                image_url=None,
                ocr_raw_text=None,
                created_by_id=1,
            )
        ],
    )

    response = client.get("/api/products", headers=AUTH_HEADERS)
    clear_overrides()

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == 101


def test_list_products_filters_by_barcode(monkeypatch) -> None:
    db = FakeSession()
    install_authenticated_overrides(db)

    def fake_get_products(_db: FakeSession, *, facility_id: int, barcode: str | None = None) -> list[SimpleNamespace]:
        assert facility_id == 1
        assert barcode == "880100000101"
        return [
            SimpleNamespace(
                id=101,
                facility_id=1,
                name="Kids Pure Wipes",
                category="WET_TISSUE",
                manufacturer="Sample Care",
                barcode="880100000101",
                expiry_date=None,
                raw_ingredients_text=None,
                ingredients=["purified water"],
                normalized_ingredients=["purified water"],
                image_url=None,
                ocr_raw_text=None,
                created_by_id=1,
            )
        ]

    monkeypatch.setattr(products_route, "get_products", fake_get_products)

    response = client.get(
        "/api/products",
        headers=AUTH_HEADERS,
        params={"barcode": "880100000101"},
    )
    clear_overrides()

    assert response.status_code == 200
    assert response.json()[0]["barcode"] == "880100000101"


def test_list_products_with_unknown_barcode_returns_empty_list(monkeypatch) -> None:
    db = FakeSession()
    install_authenticated_overrides(db)

    monkeypatch.setattr(products_route, "get_products", lambda _db, *, facility_id, barcode=None: [])

    response = client.get(
        "/api/products",
        headers=AUTH_HEADERS,
        params={"barcode": "9999999999999"},
    )
    clear_overrides()

    assert response.status_code == 200
    assert response.json() == []


def test_list_products_with_blank_barcode_returns_bad_request(monkeypatch) -> None:
    db = FakeSession()
    install_authenticated_overrides(db)

    def fake_get_products(_db: FakeSession, *, facility_id: int, barcode: str | None = None) -> list[SimpleNamespace]:
        raise InvalidBarcodeError("Barcode must not be empty")

    monkeypatch.setattr(products_route, "get_products", fake_get_products)

    response = client.get(
        "/api/products",
        headers=AUTH_HEADERS,
        params={"barcode": "   "},
    )
    clear_overrides()

    assert response.status_code == 400
    assert response.json()["error"]["message"] == "Barcode must not be empty"


def test_list_products_without_token() -> None:
    db = FakeSession()
    install_db_override(db)

    response = client.get("/api/products")
    clear_overrides()

    assert response.status_code == 401


def test_get_product_success() -> None:
    db = FakeSession()
    db.scalar_result = Product(
        id=101,
        facility_id=1,
        name="Kids Pure Wipes",
        category="WET_TISSUE",
        manufacturer="Sample Care",
        barcode="880100000101",
        ingredients=["purified water"],
        normalized_ingredients=["purified water"],
        created_by_id=1,
    )
    install_authenticated_overrides(db)

    response = client.get("/api/products/101", headers=AUTH_HEADERS)
    clear_overrides()

    assert response.status_code == 200
    assert response.json()["id"] == 101


def test_get_product_not_found() -> None:
    db = FakeSession()
    install_authenticated_overrides(db)

    response = client.get("/api/products/9999", headers=AUTH_HEADERS)
    clear_overrides()

    assert response.status_code == 404


def test_create_product_success(monkeypatch) -> None:
    db = FakeSession()
    install_authenticated_overrides(db)

    monkeypatch.setattr(
        products_route,
        "normalize_ingredients",
        lambda _db, ingredients: ingredients,
    )

    response = client.post(
        "/api/products",
        headers=AUTH_HEADERS,
        json={
            "name": "Test Kids Lotion",
            "category": "LOTION",
            "manufacturer": "Test Manufacturer",
            "barcode": "880000009999",
            "expiry_date": "2027-12-31",
            "raw_ingredients_text": "purified water, glycerin, fragrance, ethanol",
            "ingredients": ["purified water", "glycerin", "fragrance", "ethanol"],
        },
    )
    clear_overrides()

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Kids Lotion"
    assert data["facility_id"] == 1
    assert data["created_by_id"] == 1
    assert db.committed is True
    assert db.refreshed is True


def test_create_product_without_token() -> None:
    db = FakeSession()
    install_db_override(db)

    response = client.post(
        "/api/products",
        json={
            "name": "Test Kids Lotion",
            "category": "LOTION",
            "ingredients": ["purified water"],
        },
    )
    clear_overrides()

    assert response.status_code == 401


def test_create_product_normalizes_ingredient_alias(monkeypatch) -> None:
    db = FakeSession()
    install_authenticated_overrides(db)

    monkeypatch.setattr(
        products_route,
        "normalize_ingredients",
        lambda _db, ingredients: ["purified water", "caseinate"],
    )

    response = client.post(
        "/api/products",
        headers=AUTH_HEADERS,
        json={
            "name": "Casein Test Wipes",
            "category": "WET_TISSUE",
            "manufacturer": "Test Manufacturer",
            "barcode": "880000001234",
            "expiry_date": "2027-12-31",
            "raw_ingredients_text": "purified water, caseinNa",
            "ingredients": ["purified water", "caseinNa"],
        },
    )
    clear_overrides()

    assert response.status_code == 201
    data = response.json()
    assert data["ingredients"] == ["purified water", "caseinNa"]
    assert data["normalized_ingredients"] == ["purified water", "caseinate"]
