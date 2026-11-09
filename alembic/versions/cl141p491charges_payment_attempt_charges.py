"""CL141: historial individual de transacciones Mercado Pago.

Cada PaymentAttempt puede asociarse a varias transacciones
externas. No modifica payments ni reconoce ingresos por si sola.
"""

from alembic import op
import sqlalchemy as sa

revision = "cl141p491charges"
down_revision = "cl141p479attempts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_attempt_charges",
        sa.Column(
            "id", sa.Integer(), primary_key=True
        ),
        sa.Column(
            "attempt_id",
            sa.Integer(),
            sa.ForeignKey(
                "payment_attempts.id", ondelete="RESTRICT"
            ),
            nullable=False,
        ),
        sa.Column(
            "mp_payment_id", sa.String(120), nullable=False
        ),
        sa.Column(
            "status", sa.String(32), nullable=False
        ),
        sa.Column(
            "amount", sa.Numeric(10, 2), nullable=True
        ),
        sa.Column(
            "currency", sa.String(3), nullable=True
        ),
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
            "mp_payment_id",
            name="uq_payment_attempt_charges_mp_payment_id",
        ),
        sa.CheckConstraint(
            "amount IS NULL OR amount >= 0",
            name="ck_payment_attempt_charges_amount",
        ),
    )
    op.create_index(
        "ix_payment_attempt_charges_attempt_created",
        "payment_attempt_charges",
        ["attempt_id", "created_at"],
    )


def downgrade() -> None:
    raise RuntimeError(
        "El historial de cobros externos no debe eliminarse "
        "sin un procedimiento de conservacion de datos."
    )
