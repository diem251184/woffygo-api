"""Transport delivery security.

Revision ID: cl145transportdelivery
Revises: cl145paymentorigin
"""

from alembic import op
import sqlalchemy as sa

revision = "cl145transportdelivery"
down_revision = "cl145paymentorigin"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "walk_locations",
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "walk_locations",
        sa.Column(
            "is_mocked",
            sa.Boolean(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_walk_locations_delivery_evidence",
        "walk_locations",
        ["walk_id", "recorded_at", "id"],
        unique=False,
    )

    op.create_table(
        "transport_delivery_credentials",

        sa.Column(
            "booking_id",
            sa.Integer(),
            sa.ForeignKey(
                "bookings.id",
                ondelete="CASCADE",
            ),
            primary_key=True,
        ),

        sa.Column(
            "pin_verifier",
            sa.String(128),
            nullable=False,
        ),

        sa.Column(
            "generation_nonce",
            sa.String(64),
            nullable=False,
        ),

        sa.Column(
            "key_version",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),

        sa.Column(
            "failed_attempts",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),

        sa.Column(
            "locked_until",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "used_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "invalidated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.CheckConstraint(
            "failed_attempts >= 0",
            name="ck_delivery_attempts_nonnegative",
        ),

        sa.CheckConstraint(
            "key_version > 0",
            name="ck_delivery_key_version_positive",
        ),

        sa.CheckConstraint(
            "char_length(pin_verifier) = 64",
            name="ck_delivery_verifier_length",
        ),

        sa.CheckConstraint(
            "char_length(generation_nonce) = 64",
            name="ck_delivery_nonce_length",
        ),

        sa.CheckConstraint(
            "used_at IS NULL OR used_at >= created_at",
            name="ck_delivery_used_after_creation",
        ),

        sa.CheckConstraint(
            "invalidated_at IS NULL "
            "OR invalidated_at >= created_at",
            name="ck_delivery_invalidated_after_creation",
        ),
    )


def downgrade():
    raise RuntimeError(
        "Unsafe downgrade: delivery security evidence "
        "must not be deleted automatically."
    )
