from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "message": "Ddakkok API is running",
    }


@router.get("/health/db")
def database_health_check(db: Annotated[Session, Depends(get_db)]):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection failed",
        ) from exc

    return {
        "status": "ok",
        "database": "connected",
    }
