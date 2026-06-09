from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.child import Child
    from app.models.classroom import Classroom
    from app.models.product import Product
    from app.models.user import User


class Facility(Base, TimestampMixin):
    __tablename__ = "facilities"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    facility_type: Mapped[str] = mapped_column(
        String(30),
        default="DAYCARE",
        nullable=False,
    )
    address: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(30))

    classrooms: Mapped[list[Classroom]] = relationship(
        "Classroom",
        back_populates="facility",
    )
    children: Mapped[list[Child]] = relationship(
        "Child",
        back_populates="facility",
    )
    products: Mapped[list[Product]] = relationship(
        "Product",
        back_populates="facility",
    )
    users: Mapped[list[User]] = relationship(
        "User",
        back_populates="facility",
    )
