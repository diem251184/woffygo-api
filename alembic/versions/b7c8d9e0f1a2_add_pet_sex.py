"""Add nullable sex field to pets.

Revision ID: b7c8d9e0f1a2
Revises: f6a7b8c9d0e1
"""

from alembic import op
import sqlalchemy as sa

revision = "b7c8d9e0f1a2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pets",
        sa.Column("sex", sa.String(length=10), nullable=True),
    )
    op.create_check_constraint(
        "ck_pets_sex_allowed",
        "pets",
        "sex IS NULL OR sex IN ('male', 'female')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_pets_sex_allowed",
        "pets",
        type_="check",
    )
    op.drop_column("pets", "sex")
