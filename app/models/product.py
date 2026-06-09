from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.facility import Facility
    from app.models.safety_check import SafetyCheck
    from app.models.user import User


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("facilities.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(100))
    barcode: Mapped[str | None] = mapped_column(String(100))
    expiry_date: Mapped[date | None] = mapped_column(Date)
    raw_ingredients_text: Mapped[str | None] = mapped_column(Text)
    ingredients: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    normalized_ingredients: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    image_url: Mapped[str | None] = mapped_column(String(500))
    ocr_raw_text: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    facility: Mapped[Facility] = relationship(
        "Facility",
        back_populates="products",
    )
    created_by: Mapped[User | None] = relationship("User")
    safety_checks: Mapped[list[SafetyCheck]] = relationship(
        "SafetyCheck",
        back_populates="product",
    )


class IngredientAlias(Base, TimestampMixin):
    __tablename__ = "ingredient_aliases"

    id: Mapped[int] = mapped_column(primary_key=True)
    alias: Mapped[str] = mapped_column(String(100), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(100), nullable=False)
