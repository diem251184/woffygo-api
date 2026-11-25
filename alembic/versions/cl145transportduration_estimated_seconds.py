"""Persist estimated road duration for transport bookings."""

from alembic import op
import sqlalchemy as sa


revision = "cl145transportduration"
down_revision = "cl145etaquota"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "bookings",
        sa.Column(
            "estimated_transport_seconds",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_check_constraint(
        "ck_bookings_estimated_transport_seconds",
        "bookings",
        "estimated_transport_seconds IS NULL OR "
        "(service_type = 'TRANSPORT' "
        "AND estimated_transport_seconds >= 0)",
    )


def downgrade():
    op.drop_constraint(
        "ck_bookings_estimated_transport_seconds",
        "bookings",
        type_="check",
    )

    op.drop_column(
        "bookings",
        "estimated_transport_seconds",
    )
