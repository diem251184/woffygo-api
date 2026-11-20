"""Create private pet health documents.

Revision ID: cl143pethealthdocs
Revises: cl142specialneeds
"""

from alembic import op
import sqlalchemy as sa


revision = "cl143pethealthdocs"
down_revision = "cl142specialneeds"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pet_health_documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("pet_id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["pet_id"],
            ["pets.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "public_id",
            name="uq_pet_health_documents_public_id",
        ),
    )

    op.create_index(
        "ix_pet_health_documents_pet_id",
        "pet_health_documents",
        ["pet_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_pet_health_documents_pet_id",
        table_name="pet_health_documents",
    )
    op.drop_table("pet_health_documents")
