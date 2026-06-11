from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.child import Child
from app.models.classroom import Classroom
from app.models.user import User


class ClassroomNotFoundError(ValueError):
    """Raised when a classroom is not accessible to the current user."""


class ChildNotFoundError(ValueError):
    """Raised when a child is not accessible to the current user."""


def get_classroom_children(
    db: Session,
    current_user: User,
    classroom_id: int,
) -> tuple[Classroom, list[Child]]:
    classroom = db.scalar(
        select(Classroom).where(
            Classroom.id == classroom_id,
            Classroom.facility_id == current_user.facility_id,
        )
    )

    if classroom is None:
        raise ClassroomNotFoundError("Classroom not found")

    children = db.scalars(
        select(Child)
        .where(
            Child.classroom_id == classroom_id,
            Child.facility_id == current_user.facility_id,
            Child.is_active.is_(True),
        )
        .order_by(Child.id.asc())
    ).all()

    return classroom, children


def get_child_detail(
    db: Session,
    current_user: User,
    child_id: int,
) -> Child:
    child = db.scalar(
        select(Child)
        .options(selectinload(Child.health_profile))
        .where(
            Child.id == child_id,
            Child.facility_id == current_user.facility_id,
            Child.is_active.is_(True),
        )
    )

    if child is None:
        raise ChildNotFoundError("Child not found")

    return child
