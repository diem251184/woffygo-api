"""Add pet species and optional PPP/provider preferences.

Revision ID: f6a7b8c9d0e1
Revises: a9b8c7d6e5f4
"""

from alembic import op
import sqlalchemy as sa

revision = "f6a7b8c9d0e1"
down_revision = "a9b8c7d6e5f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pets",
        sa.Column("species", sa.String(length=10), nullable=False, server_default="dog"),
    )
    op.add_column(
        "pets",
        sa.Column("is_ppp", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "walker_profiles",
        sa.Column("accepts_ppp", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "walker_profiles",
        sa.Column("accepts_cats", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("walker_profiles", "accepts_cats")
    op.drop_column("walker_profiles", "accepts_ppp")
    op.drop_column("pets", "is_ppp")
    op.drop_column("pets", "species")
