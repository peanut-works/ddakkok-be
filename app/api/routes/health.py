from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.error import ErrorResponse
from app.schemas.health import DatabaseHealthResponse, HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="API health check",
    responses={
        500: {
            "model": ErrorResponse,
            "description": "Internal server error",
        }
    },
)
def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        message="Ddakkok API is running",
    )


@router.get(
    "/health/db",
    response_model=DatabaseHealthResponse,
    summary="Database connection health check",
    responses={
        500: {
            "model": ErrorResponse,
            "description": "Database connection failed",
        }
    },
)
def database_health_check(db: Annotated[Session, Depends(get_db)]) -> DatabaseHealthResponse:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection failed",
        ) from exc

    return DatabaseHealthResponse(
        status="ok",
        database="connected",
    )
