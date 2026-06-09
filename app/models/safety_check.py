from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.child import Child
    from app.models.classroom import Classroom
    from app.models.facility import Facility
    from app.models.product import Product
    from app.models.user import User


class SafetyCheck(Base, TimestampMixin):
    __tablename__ = "safety_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("facilities.id"),
        nullable=False,
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"),
        nullable=False,
    )
    classroom_id: Mapped[int | None] = mapped_column(ForeignKey("classrooms.id"))
    requested_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    overall_status: Mapped[str] = mapped_column(String(20), nullable=False)
    pass_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warn_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expired_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unknown_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    facility: Mapped[Facility] = relationship("Facility")
    product: Mapped[Product] = relationship(
        "Product",
        back_populates="safety_checks",
    )
    classroom: Mapped[Classroom | None] = relationship("Classroom")
    requested_by: Mapped[User | None] = relationship("User")
    results: Mapped[list[SafetyCheckResult]] = relationship(
        "SafetyCheckResult",
        back_populates="safety_check",
    )


class SafetyCheckResult(Base, TimestampMixin):
    __tablename__ = "safety_check_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    safety_check_id: Mapped[int] = mapped_column(
        ForeignKey("safety_checks.id"),
        nullable=False,
    )
    child_id: Mapped[int] = mapped_column(
        ForeignKey("children.id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    matched_rule_code: Mapped[str | None] = mapped_column(String(50))
    matched_profile: Mapped[str | None] = mapped_column(String(100))
    matched_ingredient: Mapped[str | None] = mapped_column(String(100))
    reason: Mapped[str | None] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)

    safety_check: Mapped[SafetyCheck] = relationship(
        "SafetyCheck",
        back_populates="results",
    )
    child: Mapped[Child] = relationship(
        "Child",
        back_populates="safety_check_results",
    )
