"""Persistir destino geográfico y dirección de Woofy Traslados.

Las reservas históricas conservan NULL.
No se reconstruyen coordenadas a partir de observaciones.
"""

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geography

revision = "cl145transportdestination"
down_revision = "cl145petconditions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bookings",
        sa.Column(
            "dropoff_location",
            Geography(
                geometry_type="POINT",
                srid=4326,
                spatial_index=False,
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "bookings",
        sa.Column(
            "dropoff_address",
            sa.String(length=255),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("bookings", "dropoff_address")
    op.drop_column("bookings", "dropoff_location")