"""add service type safely

Revision ID: e5d4c3b2a1f0
Revises: c9b8a7f6e5d4
Create Date: 2026-10-28 23:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e5d4c3b2a1f0'
down_revision = 'c9b8a7f6e5d4'
branch_labels = None
depends_on = None

def upgrade():
    # Solo agregamos la columna service_type a users
    op.add_column('users', sa.Column('service_type', sa.String(length=50), nullable=False, server_default='walk'))

def downgrade():
    op.drop_column('users', 'service_type')
