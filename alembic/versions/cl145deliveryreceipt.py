"""Independent transport delivery receipt."""

from alembic import op
import sqlalchemy as sa

revision = "cl145deliveryreceipt"
down_revision = "cl145transportdelivery"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "transport_delivery_credentials",
        sa.Column(
            "owner_received_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_check_constraint(
        "ck_delivery_owner_receipt",
        "transport_delivery_credentials",
        "owner_received_at IS NULL OR "
        "(used_at IS NOT NULL "
        "AND invalidated_at IS NULL "
        "AND owner_received_at >= used_at)",
    )


def downgrade():
    raise RuntimeError(
        "Delivery receipt evidence must not "
        "be deleted automatically."
    )
