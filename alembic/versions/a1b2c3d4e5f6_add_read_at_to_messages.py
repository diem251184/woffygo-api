"""add read_at to messages

Revision ID: a1b2c3d4e5f6
Revises: 335361bd2658
Create Date: 2026-09-26 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '335361bd2658'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'messages',
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f('ix_messages_read_at'),
        'messages',
        ['read_at'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_messages_read_at'), table_name='messages')
    op.drop_column('messages', 'read_at')