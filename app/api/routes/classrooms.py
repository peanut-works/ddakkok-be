from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.params import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.classroom import Classroom
from app.models.user import User
from app.schemas.classroom import ClassroomResponse
from app.services.auth import parse_mock_access_token

router = APIRouter(prefix="/api/classrooms", tags=["classrooms"])


@router.get("", response_model=list[ClassroomResponse])
def list_classrooms(
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> list[ClassroomResponse]:
    user_id = parse_mock_access_token(authorization)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing access token",
        )

    user = db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing access token",
        )

    classrooms = db.scalars(
        select(Classroom)
        .where(Classroom.facility_id == user.facility_id)
        .order_by(Classroom.id.asc())
    ).all()

    return classrooms