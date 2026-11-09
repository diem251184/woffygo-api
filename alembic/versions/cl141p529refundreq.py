"""Persistencia de solicitudes de reembolso total.

Revision ID: cl141p529refundreq
Revises: cl141p491charges
"""

from alembic import op
import sqlalchemy as sa

revision = "cl141p529refundreq"
down_revision = "cl141p491charges"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "payment_refund_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "payment_id",
            sa.Integer(),
            sa.ForeignKey("payments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("mp_payment_id", sa.String(120), nullable=False),
        sa.Column("idempotency_key", sa.String(36), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="prepared",
        ),
        sa.Column("mp_refund_id", sa.String(120), nullable=True),
        sa.Column("response_http_status", sa.Integer(), nullable=True),
        sa.Column("response_status", sa.String(80), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "mp_payment_id",
            name="uq_refund_requests_mp_payment_id",
        ),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_refund_requests_idempotency_key",
        ),
    )
    op.create_index(
        "ix_refund_requests_payment_id",
        "payment_refund_requests",
        ["payment_id"],
    )


def downgrade():
    op.drop_index(
        "ix_refund_requests_payment_id",
        table_name="payment_refund_requests",
    )
    op.drop_table("payment_refund_requests")
