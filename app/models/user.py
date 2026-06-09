from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.classroom import Classroom
    from app.models.facility import Facility


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("facilities.id"),
        nullable=False,
    )
    classroom_id: Mapped[int | None] = mapped_column(ForeignKey("classrooms.id"))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    role: Mapped[str] = mapped_column(String(30), default="TEACHER", nullable=False)

    facility: Mapped[Facility] = relationship(
        "Facility",
        back_populates="users",
    )
    classroom: Mapped[Classroom | None] = relationship(
        "Classroom",
        back_populates="users",
    )
