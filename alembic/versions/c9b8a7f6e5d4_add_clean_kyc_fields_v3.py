"""add clean kyc fields v3

Revision ID: c9b8a7f6e5d4
Revises: 310cf3d27569
Create Date: 2026-10-28 22:50:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c9b8a7f6e5d4'
down_revision = '310cf3d27569'
branch_labels = None
depends_on = None

def upgrade():
    # 1. PRIMERO: Crear el tipo Enum en PostgreSQL
    document_status_enum = sa.Enum('missing', 'pending', 'approved', 'rejected', 'expired', name='document_status')
    document_status_enum.create(op.get_bind(), checkfirst=True)

    # 2. Hacer que los DNI y la Selfie sean opcionales
    op.alter_column('walker_verifications', 'dni_front_url', existing_type=sa.String(length=500), nullable=True)
    op.alter_column('walker_verifications', 'dni_back_url', existing_type=sa.String(length=500), nullable=True)
    op.alter_column('walker_verifications', 'selfie_url', existing_type=sa.String(length=500), nullable=True)

    # 3. Bloque Identidad
    op.add_column('walker_verifications', sa.Column('identity_status', document_status_enum, nullable=False, server_default='missing'))
    op.add_column('walker_verifications', sa.Column('identity_rejection_reason', sa.Text(), nullable=True))

    # 4. Bloque Licencia
    op.add_column('walker_verifications', sa.Column('license_status', document_status_enum, nullable=False, server_default='missing'))
    op.add_column('walker_verifications', sa.Column('license_number', sa.String(length=50), nullable=True))
    op.add_column('walker_verifications', sa.Column('license_class', sa.String(length=50), nullable=True))
    op.add_column('walker_verifications', sa.Column('license_jurisdiction', sa.String(length=100), nullable=True))
    op.add_column('walker_verifications', sa.Column('license_expiration', sa.Date(), nullable=True))
    op.add_column('walker_verifications', sa.Column('license_front_url', sa.String(length=500), nullable=True))
    op.add_column('walker_verifications', sa.Column('license_back_url', sa.String(length=500), nullable=True))
    op.add_column('walker_verifications', sa.Column('license_rejection_reason', sa.Text(), nullable=True))

    # 5. Bloque Vehiculo
    op.add_column('walker_verifications', sa.Column('vehicle_status', document_status_enum, nullable=False, server_default='missing'))
    op.add_column('walker_verifications', sa.Column('vehicle_plate', sa.String(length=20), nullable=True))
    op.add_column('walker_verifications', sa.Column('vehicle_brand', sa.String(length=50), nullable=True))
    op.add_column('walker_verifications', sa.Column('vehicle_model', sa.String(length=50), nullable=True))
    op.add_column('walker_verifications', sa.Column('vehicle_year', sa.Integer(), nullable=True))
    op.add_column('walker_verifications', sa.Column('vehicle_photo_url', sa.String(length=500), nullable=True))
    op.add_column('walker_verifications', sa.Column('vehicle_cedula_url', sa.String(length=500), nullable=True))
    op.add_column('walker_verifications', sa.Column('vehicle_insurance_url', sa.String(length=500), nullable=True))
    op.add_column('walker_verifications', sa.Column('vehicle_inspection_url', sa.String(length=500), nullable=True))
    op.add_column('walker_verifications', sa.Column('vehicle_rejection_reason', sa.Text(), nullable=True))

def downgrade():
    # Borrar columnas
    op.drop_column('walker_verifications', 'vehicle_rejection_reason')
    op.drop_column('walker_verifications', 'vehicle_inspection_url')
    op.drop_column('walker_verifications', 'vehicle_insurance_url')
    op.drop_column('walker_verifications', 'vehicle_cedula_url')
    op.drop_column('walker_verifications', 'vehicle_photo_url')
    op.drop_column('walker_verifications', 'vehicle_year')
    op.drop_column('walker_verifications', 'vehicle_model')
    op.drop_column('walker_verifications', 'vehicle_brand')
    op.drop_column('walker_verifications', 'vehicle_plate')
    op.drop_column('walker_verifications', 'vehicle_status')
    op.drop_column('walker_verifications', 'license_rejection_reason')
    op.drop_column('walker_verifications', 'license_back_url')
    op.drop_column('walker_verifications', 'license_front_url')
    op.drop_column('walker_verifications', 'license_expiration')
    op.drop_column('walker_verifications', 'license_jurisdiction')
    op.drop_column('walker_verifications', 'license_class')
    op.drop_column('walker_verifications', 'license_number')
    op.drop_column('walker_verifications', 'license_status')
    op.drop_column('walker_verifications', 'identity_rejection_reason')
    op.drop_column('walker_verifications', 'identity_status')

    # Borrar el tipo Enum
    document_status_enum = sa.Enum('missing', 'pending', 'approved', 'rejected', 'expired', name='document_status')
    document_status_enum.drop(op.get_bind(), checkfirst=True)

    # Restaurar NOT NULL en los DNI y Selfie
    op.alter_column('walker_verifications', 'selfie_url', existing_type=sa.String(length=500), nullable=False)
    op.alter_column('walker_verifications', 'dni_back_url', existing_type=sa.String(length=500), nullable=False)
    op.alter_column('walker_verifications', 'dni_front_url', existing_type=sa.String(length=500), nullable=False)
