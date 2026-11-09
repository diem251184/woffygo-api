"""add location to safety

Revision ID: a9b8c7d6e5f4
Revises: e5d4c3b2a1f0
Create Date: 2026-10-29 01:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2

revision = 'a9b8c7d6e5f4'
down_revision = 'e5d4c3b2a1f0'
branch_labels = None
depends_on = None

def upgrade():
    # Agregar la columna location de PostGIS
    op.add_column('safety_reports', sa.Column('location', geoalchemy2.types.Geography(geometry_type='POINT', srid=4326), nullable=True))

def downgrade():
    op.drop_column('safety_reports', 'location')
