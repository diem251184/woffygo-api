"""Add scheduled pickup time to bookings."""

from alembic import op
import sqlalchemy as sa


revision = "cl145scheduledpickup"
down_revision = "cl145transportdestination"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "bookings",
        sa.Column(
            "scheduled_pickup_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("bookings", "scheduled_pickup_at")
