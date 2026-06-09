from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.child import Child
    from app.models.facility import Facility


class Classroom(Base, TimestampMixin):
    __tablename__ = "classrooms"

    id: Mapped[int] = mapped_column(primary_key=True)
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("facilities.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    age_group: Mapped[str | None] = mapped_column(String(30))

    facility: Mapped[Facility] = relationship(
        "Facility",
        back_populates="classrooms",
    )
    children: Mapped[list[Child]] = relationship(
        "Child",
        back_populates="classroom",
    )
