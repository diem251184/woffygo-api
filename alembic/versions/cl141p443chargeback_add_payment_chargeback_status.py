"""Agregar estado contracargo a payment_status.

Revision ID: cl141p443chargeback
Revises: cl141p415dispmeta

El cambio no altera pagos existentes.
"""

from alembic import op

revision = "cl141p443chargeback"
down_revision = "cl141p415dispmeta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE payment_status "
        "ADD VALUE IF NOT EXISTS 'contracargo'"
    )


def downgrade() -> None:
    # PostgreSQL no permite eliminar directamente un valor
    # del enum sin recrear el tipo y revisar los datos.
    # Evitar un downgrade destructivo o silencioso.
    raise RuntimeError(
        "Downgrade bloqueado: requiere procedimiento "
        "explicito de preservacion de datos."
    )
