"""add safety fields to pets

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-27 02:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('pets', sa.Column('size', sa.String(length=20), nullable=True))
    op.add_column('pets', sa.Column('weight_kg', sa.Float(), nullable=True))
    op.add_column(
        'pets',
        sa.Column('aggressive_with_dogs', sa.Boolean(), nullable=False, server_default='false'),
    )
    op.add_column(
        'pets',
        sa.Column('aggressive_with_people', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade() -> None:
    op.drop_column('pets', 'aggressive_with_people')
    op.drop_column('pets', 'aggressive_with_dogs')
    op.drop_column('pets', 'weight_kg')
    op.drop_column('pets', 'size')