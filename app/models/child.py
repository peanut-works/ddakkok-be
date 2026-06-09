from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.classroom import Classroom
    from app.models.facility import Facility
    from app.models.safety_check import SafetyCheckResult


class Child(Base, TimestampMixin):
    __tablename__ = "children"

    id: Mapped[int] = mapped_column(primary_key=True)
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("facilities.id"),
        nullable=False,
    )
    classroom_id: Mapped[int] = mapped_column(
        ForeignKey("classrooms.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    birth_date: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(10))
    memo: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    facility: Mapped[Facility] = relationship(
        "Facility",
        back_populates="children",
    )
    classroom: Mapped[Classroom] = relationship(
        "Classroom",
        back_populates="children",
    )
    health_profile: Mapped[ChildHealthProfile | None] = relationship(
        "ChildHealthProfile",
        back_populates="child",
        uselist=False,
    )
    safety_check_results: Mapped[list[SafetyCheckResult]] = relationship(
        "SafetyCheckResult",
        back_populates="child",
    )


class ChildHealthProfile(Base, TimestampMixin):
    __tablename__ = "child_health_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(
        ForeignKey("children.id"),
        unique=True,
        nullable=False,
    )
    allergies: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    skin_conditions: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    sensitive_ingredients: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text)

    child: Mapped[Child] = relationship(
        "Child",
        back_populates="health_profile",
    )
