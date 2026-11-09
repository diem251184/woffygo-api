"""CL141: identificador unico de pago de Mercado Pago.

Revision ID: cl141p336mpuniq
Revises: b7c8d9e0f1a2

No modifica importes ni registros existentes.
PostgreSQL permite multiples NULL en un indice UNIQUE.
"""

from alembic import op

revision = "cl141p336mpuniq"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index(
        "ix_payments_mp_payment_id",
        table_name="payments",
    )
    op.create_index(
        "ix_payments_mp_payment_id",
        "payments",
        ["mp_payment_id"],
        unique=True,
    )


def downgrade():
    op.drop_index(
        "ix_payments_mp_payment_id",
        table_name="payments",
    )
    op.create_index(
        "ix_payments_mp_payment_id",
        "payments",
        ["mp_payment_id"],
        unique=False,
    )
