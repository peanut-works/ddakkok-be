from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.exceptions import register_exception_handlers


def create_test_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/http-error")
    def http_error() -> None:
        raise HTTPException(status_code=404, detail="Item not found")

    @app.get("/validation-error")
    def validation_error(limit: int) -> dict[str, int]:
        return {"limit": limit}

    @app.get("/unhandled-error")
    def unhandled_error() -> None:
        raise RuntimeError("boom")

    return app


def test_http_exception_uses_common_error_response() -> None:
    client = TestClient(create_test_app())

    response = client.get("/http-error")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "NOT_FOUND",
            "message": "Item not found",
            "details": None,
        }
    }


def test_validation_error_uses_common_error_response() -> None:
    client = TestClient(create_test_app())

    response = client.get("/validation-error", params={"limit": "invalid"})
    payload = response.json()

    assert response.status_code == 422
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["error"]["message"] == "Request validation failed"
    assert payload["error"]["details"][0]["loc"] == ["query", "limit"]


def test_unhandled_exception_uses_common_error_response() -> None:
    client = TestClient(create_test_app(), raise_server_exceptions=False)

    response = client.get("/unhandled-error")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "Internal server error",
            "details": None,
        }
    }
