"""CL141: registrar intentos individuales de cobro.

La tabla no modifica payments ni activa nuevos checkouts.
Cada intento pertenece a un Payment principal existente.
"""

from alembic import op
import sqlalchemy as sa

revision = "cl141p479attempts"
down_revision = "cl141p454payevents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "payment_id",
            sa.Integer(),
            sa.ForeignKey("payments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("attempt_key", sa.String(64), nullable=False),
        sa.Column("mp_preference_id", sa.String(120), nullable=True),
        sa.Column("mp_payment_id", sa.String(120), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="created",
        ),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "attempt_key",
            name="uq_payment_attempts_attempt_key",
        ),
        sa.UniqueConstraint(
            "mp_preference_id",
            name="uq_payment_attempts_mp_preference",
        ),
        sa.UniqueConstraint(
            "mp_payment_id",
            name="uq_payment_attempts_mp_payment",
        ),
        sa.CheckConstraint(
            "amount > 0",
            name="ck_payment_attempts_amount_positive",
        ),
    )

    op.create_index(
        "ix_payment_attempts_payment_created",
        "payment_attempts",
        ["payment_id", "created_at"],
    )


def downgrade() -> None:
    raise RuntimeError(
        "La eliminacion de intentos financieros requiere "
        "un procedimiento de conservacion de datos."
    )
