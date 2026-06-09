from __future__ import annotations

from sqlalchemy import JSON, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SafetyRule(Base, TimestampMixin):
    __tablename__ = "safety_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    trigger_name: Mapped[str] = mapped_column(String(100), nullable=False)
    ingredient_keywords: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    source_name: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
