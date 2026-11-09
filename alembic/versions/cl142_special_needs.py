"""CL142 - Necesidades especiales de mascotas y prestadores."""

from alembic import op
import sqlalchemy as sa

revision = "cl142specialneeds"
down_revision = "cl141p529refundreq"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pets",
        sa.Column(
            "has_special_needs",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.add_column(
        "walker_profiles",
        sa.Column(
            "accepts_special_needs",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("walker_profiles", "accepts_special_needs")
    op.drop_column("pets", "has_special_needs")
