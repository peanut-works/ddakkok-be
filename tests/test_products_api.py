from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_list_products_success():
    response = client.get(
        "/api/products",
        headers={"Authorization": "Bearer mock-token:user:1"},
    )

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)
    assert len(data) > 0

    first_product = data[0]

    assert "id" in first_product
    assert "facility_id" in first_product
    assert "name" in first_product
    assert "category" in first_product
    assert "ingredients" in first_product
    assert "normalized_ingredients" in first_product


def test_list_products_without_token():
    response = client.get("/api/products")

    assert response.status_code == 401


def test_get_product_success():
    response = client.get(
        "/api/products/101",
        headers={"Authorization": "Bearer mock-token:user:1"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == 101
    assert data["facility_id"] == 1
    assert "name" in data
    assert "ingredients" in data


def test_get_product_not_found():
    response = client.get(
        "/api/products/9999",
        headers={"Authorization": "Bearer mock-token:user:1"},
    )

    assert response.status_code == 404


def test_create_product_success():
    response = client.post(
        "/api/products",
        headers={"Authorization": "Bearer mock-token:user:1"},
        json={
            "name": "테스트 키즈 로션",
            "category": "LOTION",
            "manufacturer": "테스트제조사",
            "barcode": "880000009999",
            "expiry_date": "2027-12-31",
            "raw_ingredients_text": "정제수, 글리세린, 향료, 에탄올",
            "ingredients": ["정제수", "글리세린", "향료", "에탄올"],
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["name"] == "테스트 키즈 로션"
    assert data["facility_id"] == 1
    assert data["created_by_id"] == 1
    assert data["ingredients"] == ["정제수", "글리세린", "향료", "에탄올"]
    assert data["normalized_ingredients"] == ["정제수", "글리세린", "향료", "에탄올"]


def test_create_product_without_token():
    response = client.post(
        "/api/products",
        json={
            "name": "테스트 키즈 로션",
            "category": "LOTION",
            "ingredients": ["정제수"],
        },
    )

    assert response.status_code == 401


def test_create_product_normalizes_ingredient_alias():
    response = client.post(
        "/api/products",
        headers={"Authorization": "Bearer mock-token:user:1"},
        json={
            "name": "카제인 테스트 물티슈",
            "category": "WET_TISSUE",
            "manufacturer": "테스트제조사",
            "barcode": "880000001234",
            "expiry_date": "2027-12-31",
            "raw_ingredients_text": "정제수, 카제인Na",
            "ingredients": ["정제수", "카제인Na"],
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["ingredients"] == ["정제수", "카제인Na"]
    assert data["normalized_ingredients"] == ["정제수", "카제인나트륨"]