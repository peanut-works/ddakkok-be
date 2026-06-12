from __future__ import annotations

import importlib
import sys
from collections.abc import Generator
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.ai.base import AIProvider, ChatMessage
from app.core.config import Settings
from app.core.exceptions import InvalidBarcodeError
from app.models.facility import Facility
from app.models.product import Product

sys.modules.pop("app.core.database", None)
database = importlib.import_module("app.core.database")
SessionLocal = database.SessionLocal

app = importlib.import_module("main").app
products_route = importlib.import_module("app.api.routes.products")

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer mock-token:user:1"}

OCR_TEXT = (
    "화장품책임판매업자:(주)코넥스앤씨 / 서울특별시 영등포구 영등포로 5길 19,1203호\n"
    "화장품제조업자:맑은미소 / 경기도 파주시 검산로 173번길 102\n"
    "사용기한 및 제조번호:별도표기 원산지:대한민국\n"
    "전성분: 정제수, 허브추출물 0.1%(로즈마리추출물, 라벤더꽃추출물, 살비아추출물,\n"
    "캐모마일꽃추출물, 페퍼민트추출물), 메틸프로판다이올, 다이프로필렌글라이콜,\n"
    "벤조익애씨드, 레블리닉애씨드, 세틸피리디늄클로라이드, 소듐벤조에이트, 향료\n"
    "유형:인체세정용물휴지 용량:[부직포]100매 [액체]480g\n"
    "품번:1025668 품명:뉴 내추럴허브물티슈100매(캡)\n"
    "사용상의 주의사항"
)


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


class FailingAIProvider(AIProvider):
    async def chat_complete(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.3,
    ) -> str:
        raise AssertionError("external AI must not be called in tests")

    async def function_call(
        self,
        messages: list[ChatMessage],
        tools: list[dict],
        tool_choice: str | dict = "auto",
    ) -> dict:
        raise RuntimeError("AI unavailable")


class StructuredAIProvider(AIProvider):
    async def chat_complete(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.3,
    ) -> str:
        raise AssertionError("parse-label-text should use function_call")

    async def function_call(
        self,
        messages: list[ChatMessage],
        tools: list[dict],
        tool_choice: str | dict = "auto",
    ) -> dict:
        return {
            "name": "AI 구조화 물티슈",
            "manufacturer": "AI제조사",
            "expiry_date": "2028-01-31",
            "raw_ingredients_text": "정제수, 소듐벤조에이트",
            "ingredients": ["정제수", "소듐벤조에이트"],
        }


def override_get_current_user() -> SimpleNamespace:
    return SimpleNamespace(id=1, facility_id=1)


def install_db_override(db: FakeSession) -> None:
    def override_get_db() -> Generator[FakeSession, None, None]:
        yield db

    app.dependency_overrides[products_route.get_db] = override_get_db


def install_authenticated_overrides(db: FakeSession) -> None:
    install_db_override(db)
    app.dependency_overrides[
        products_route.get_current_user
    ] = override_get_current_user


def clear_overrides() -> None:
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _reset_overrides() -> Generator[None, None, None]:
    yield
    clear_overrides()


def _product_count() -> int:
    db = SessionLocal()
    try:
        return int(db.scalar(select(func.count()).select_from(Product)) or 0)
    finally:
        db.close()


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

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == 101


def test_list_products_filters_by_barcode(monkeypatch) -> None:
    db = FakeSession()
    install_authenticated_overrides(db)

    def fake_get_products(
        _db: FakeSession,
        *,
        facility_id: int,
        barcode: str | None = None,
    ) -> list[SimpleNamespace]:
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

    assert response.status_code == 200
    assert response.json()[0]["barcode"] == "880100000101"


def test_list_products_with_unknown_barcode_returns_empty_list(monkeypatch) -> None:
    db = FakeSession()
    install_authenticated_overrides(db)

    monkeypatch.setattr(
        products_route,
        "get_products",
        lambda _db, *, facility_id, barcode=None: [],
    )

    response = client.get(
        "/api/products",
        headers=AUTH_HEADERS,
        params={"barcode": "9999999999999"},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_list_products_does_not_return_other_facility_products() -> None:
    db = SessionLocal()
    other_facility = Facility(
        name="다른 시설",
        address="서울시 테스트구",
        phone="02-9999-9999",
    )
    other_product = Product(
        facility=other_facility,
        name="다른 시설 제품",
        category="ETC",
        manufacturer="테스트 제조사",
        barcode="8801000001019",
        ingredients=[],
        normalized_ingredients=[],
    )

    try:
        db.add(other_facility)
        db.add(other_product)
        db.commit()
        db.refresh(other_product)
        other_product_id = other_product.id

        response = client.get(
            "/api/products",
            headers=AUTH_HEADERS,
            params={"barcode": "8801000001019"},
        )

        assert response.status_code == 200

        data = response.json()

        assert data
        assert all(item["facility_id"] == 1 for item in data)
        assert all(item["id"] != other_product_id for item in data)
    finally:
        db.delete(other_product)
        db.delete(other_facility)
        db.commit()
        db.close()


def test_list_products_with_blank_barcode_returns_bad_request(monkeypatch) -> None:
    db = FakeSession()
    install_authenticated_overrides(db)

    def fake_get_products(
        _db: FakeSession,
        *,
        facility_id: int,
        barcode: str | None = None,
    ) -> list[SimpleNamespace]:
        raise InvalidBarcodeError("Barcode must not be empty")

    monkeypatch.setattr(products_route, "get_products", fake_get_products)

    response = client.get(
        "/api/products",
        headers=AUTH_HEADERS,
        params={"barcode": "   "},
    )

    assert response.status_code == 400
    assert response.json()["error"]["message"] == "Barcode must not be empty"


def test_list_products_without_token() -> None:
    db = FakeSession()
    install_db_override(db)

    response = client.get("/api/products")

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

    assert response.status_code == 200
    assert response.json()["id"] == 101


def test_get_product_not_found() -> None:
    db = FakeSession()
    install_authenticated_overrides(db)

    response = client.get("/api/products/9999", headers=AUTH_HEADERS)

    assert response.status_code == 404


def test_parse_label_text_success_without_external_api() -> None:
    before_count = _product_count()

    app.dependency_overrides[products_route.get_settings] = lambda: Settings(
        ai_provider="mock",
    )
    app.dependency_overrides[
        products_route.get_ai_provider
    ] = lambda: FailingAIProvider()

    response = client.post(
        "/api/products/parse-label-text",
        headers=AUTH_HEADERS,
        json={
            "text": OCR_TEXT,
            "category": "WET_TISSUE",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "뉴 내추럴허브물티슈100매(캡)"
    assert data["category"] == "WET_TISSUE"
    assert data["manufacturer"].startswith("(주)코넥스앤씨")
    assert data["expiry_date"] is None
    assert "정제수" in data["ingredients"]
    assert "소듐벤조에이트" in data["ingredients"]
    assert "향료" in data["ingredients"]
    assert "카제인나트륨" not in data["ingredients"]
    assert "카제인나트륨" not in data["normalized_ingredients"]
    assert "페녹시에탄올" not in data["ingredients"]
    assert "페녹시에탄올" not in data["normalized_ingredients"]
    assert data["ocr_raw_text"] == OCR_TEXT
    assert _product_count() == before_count


def test_parse_label_text_falls_back_to_regex_without_mock_data() -> None:
    before_count = _product_count()

    app.dependency_overrides[products_route.get_settings] = lambda: Settings(
        ai_provider="openai",
    )
    app.dependency_overrides[
        products_route.get_ai_provider
    ] = lambda: FailingAIProvider()

    response = client.post(
        "/api/products/parse-label-text",
        headers=AUTH_HEADERS,
        json={
            "text": OCR_TEXT,
            "category": "WET_TISSUE",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "뉴 내추럴허브물티슈100매(캡)"
    assert "A브랜드 물티슈" not in data.values()
    assert "카제인나트륨" not in data["ingredients"]
    assert "페녹시에탄올" not in data["ingredients"]
    assert _product_count() == before_count


def test_parse_label_text_uses_structured_ai_result() -> None:
    before_count = _product_count()

    app.dependency_overrides[products_route.get_settings] = lambda: Settings(
        ai_provider="openai",
    )
    app.dependency_overrides[
        products_route.get_ai_provider
    ] = lambda: StructuredAIProvider()

    response = client.post(
        "/api/products/parse-label-text",
        headers=AUTH_HEADERS,
        json={
            "text": OCR_TEXT,
            "category": "WET_TISSUE",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "AI 구조화 물티슈"
    assert data["manufacturer"] == "AI제조사"
    assert data["expiry_date"] == "2028-01-31"
    assert data["ingredients"] == ["정제수", "소듐벤조에이트"]
    assert _product_count() == before_count


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
            "ingredients": [
                "purified water",
                "glycerin",
                "fragrance",
                "ethanol",
            ],
        },
    )

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

    assert response.status_code == 201
    data = response.json()

    assert data["ingredients"] == ["purified water", "caseinNa"]
    assert data["normalized_ingredients"] == ["purified water", "caseinate"]
