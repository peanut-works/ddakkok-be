"""add login context fields

Revision ID: 40b0a8f4e6b2
Revises: f082a7523c43
Create Date: 2026-06-10 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "40b0a8f4e6b2"
down_revision: str | Sequence[str] | None = "f082a7523c43"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "facilities",
        sa.Column(
            "facility_type",
            sa.String(length=30),
            server_default="DAYCARE",
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column("classroom_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_classroom_id_classrooms",
        "users",
        "classrooms",
        ["classroom_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_users_classroom_id_classrooms",
        "users",
        type_="foreignkey",
    )
    op.drop_column("users", "classroom_id")
    op.drop_column("facilities", "facility_type")
