"""only_add_kyc_to_users

Revision ID: 310cf3d27569
Revises: 6152c66431a2
Create Date: 2026-10-27 23:45:25.813962

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '310cf3d27569'
down_revision: Union[str, None] = '6152c66431a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    import sqlalchemy as sa
    op.add_column('users', sa.Column('kyc_status', sa.String(length=20), server_default='PENDING', nullable=False))
    op.add_column('users', sa.Column('terms_version', sa.String(length=20), nullable=True))
    op.add_column('users', sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'accepted_at')
    op.drop_column('users', 'terms_version')
    op.drop_column('users', 'kyc_status')
