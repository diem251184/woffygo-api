"""Control persistente de frecuencia para ETA de traslados."""

from alembic import op
import sqlalchemy as sa

revision = "cl145etaquota"
down_revision = "cl145scheduledpickup"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "transport_eta_rate_limits",
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "next_allowed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )


def downgrade():
    op.drop_table("transport_eta_rate_limits")
