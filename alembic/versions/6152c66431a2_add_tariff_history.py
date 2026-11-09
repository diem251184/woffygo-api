"""add_tariff_history

Revision ID: 6152c66431a2
Revises: b2c3d4e5f6a7
Create Date: 2026-10-19 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '6152c66431a2'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None

def upgrade():
    # Creamos EXCLUSIVAMENTE la tabla nueva, sin tocar las demas
    op.create_table(
        'tariff_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('service_type', sa.String(), nullable=False),
        sa.Column('base_price', sa.Float(), nullable=False),
        sa.Column('per_km_price', sa.Float(), nullable=True),
        sa.Column('extra_pet_price', sa.Float(), nullable=False),
        sa.Column('ipc_applied', sa.Float(), nullable=False),
        sa.Column('valid_from', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('valid_to', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tariff_history_id'), 'tariff_history', ['id'], unique=False)
    op.create_index(op.f('ix_tariff_history_service_type'), 'tariff_history', ['service_type'], unique=False)

def downgrade():
    op.drop_index(op.f('ix_tariff_history_service_type'), table_name='tariff_history')
    op.drop_index(op.f('ix_tariff_history_id'), table_name='tariff_history')
    op.drop_table('tariff_history')