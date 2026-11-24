"""Preserve pet conditions declared when a booking is created.

Revision ID: cl145petconditions
Revises: cl144profilereview

Existing bookings retain NULL: historical declarations are unknown.
No backfill or fabricated historical values.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "cl145petconditions"
down_revision = "cl144profilereview"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "booking_pets",
        sa.Column(
            "conditions_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("booking_pets", "conditions_snapshot")
