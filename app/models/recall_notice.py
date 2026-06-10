from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class RecallNotice(Base, TimestampMixin):
    __tablename__ = "recall_notices"

    id: Mapped[int] = mapped_column(primary_key=True)
    facility_id: Mapped[int | None] = mapped_column(ForeignKey("facilities.id"))
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[str | None] = mapped_column(String(50))
    recall_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    action_guide: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), default="Consumer24", nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500))
    external_id: Mapped[str | None] = mapped_column(String(100))
    menu_id: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
