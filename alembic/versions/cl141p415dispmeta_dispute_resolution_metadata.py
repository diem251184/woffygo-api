"""CL141: separar metadatos administrativos de Mercado Pago."""

from alembic import op
import sqlalchemy as sa

revision = "cl141p415dispmeta"
down_revision = "cl141p336mpuniq"
branch_labels = None
depends_on = None


def upgrade():
    # Adiciones opcionales: no modificar pagos existentes.
    op.add_column(
        "payments",
        sa.Column(
            "dispute_resolution_note",
            sa.String(length=120),
            nullable=True,
        ),
    )
    op.add_column(
        "payments",
        sa.Column(
            "dispute_resolved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "payments",
        sa.Column(
            "dispute_resolved_by_id",
            sa.Integer(),
            nullable=True,
        ),
    )
    op.add_column(
        "payments",
        sa.Column(
            "dispute_resolution_result",
            sa.String(length=32),
            nullable=True,
        ),
    )


def downgrade():
    # No eliminar historial administrativo registrado.
    bind = op.get_bind()
    populated = bind.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM payments
            WHERE dispute_resolution_note IS NOT NULL
               OR dispute_resolved_at IS NOT NULL
               OR dispute_resolved_by_id IS NOT NULL
               OR dispute_resolution_result IS NOT NULL
            """
        )
    ).scalar_one()

    if populated:
        raise RuntimeError(
            "Downgrade bloqueado: existen datos de resolucion "
            "de disputas que deben preservarse."
        )

    op.drop_column("payments", "dispute_resolution_result")
    op.drop_column("payments", "dispute_resolved_by_id")
    op.drop_column("payments", "dispute_resolved_at")
    op.drop_column("payments", "dispute_resolution_note")
