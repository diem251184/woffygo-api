"""Historial de transiciones de estados financieros.

Revision ID: cl141p454payevents
Revises: cl141p443chargeback

Registra transiciones futuras; no inventa eventos historicos.
No representa liquidaciones o transferencias externas.
"""

from alembic import op
import sqlalchemy as sa

revision = "cl141p454payevents"
down_revision = "cl141p443chargeback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_status_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "payment_id",
            sa.Integer(),
            sa.ForeignKey("payments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("previous_status", sa.String(32), nullable=True),
        sa.Column("new_status", sa.String(32), nullable=False),
        sa.Column("event_source", sa.String(32), nullable=False),
        sa.Column("event_key", sa.String(160), nullable=True),
        sa.Column("mp_payment_id", sa.String(120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "payment_id",
            "event_key",
            name="uq_payment_status_events_payment_key",
        ),
    )
    op.create_index(
        "ix_payment_status_events_payment_created",
        "payment_status_events",
        ["payment_id", "created_at"],
    )


def downgrade() -> None:
    raise RuntimeError(
        "Downgrade bloqueado: requiere preservacion "
        "explicita del historial financiero."
    )
