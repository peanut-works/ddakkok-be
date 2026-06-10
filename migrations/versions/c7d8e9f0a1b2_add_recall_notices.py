"""add recall_notices table

Revision ID: c7d8e9f0a1b2
Revises: b3c9d1e2f4a5
Create Date: 2026-06-11 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7d8e9f0a1b2"
down_revision: str | Sequence[str] | None = "b3c9d1e2f4a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recall_notices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("facility_id", sa.Integer(), nullable=True),
        sa.Column("product_name", sa.String(length=200), nullable=False),
        sa.Column("manufacturer", sa.String(length=100), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("recall_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("action_guide", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=50), server_default="Consumer24", nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("external_id", sa.String(length=100), nullable=True),
        sa.Column("menu_id", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("recall_notices")
