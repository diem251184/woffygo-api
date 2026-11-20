"""Add administrative review of personal profile changes.

Revision ID: cl144profilereview
Revises: cl143pethealthdocs

This migration only defines database structure.
It must not be applied before the review workflow is ready.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "cl144profilereview"
down_revision = "cl143pethealthdocs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "profile_review_status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'clear'"),
        ),
    )

    op.create_check_constraint(
        "ck_users_profile_review_status",
        "users",
        "profile_review_status IN ('clear', 'pending', 'rejected')",
    )

    op.create_table(
        "user_profile_reviews",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "previous_values",
            postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column(
            "proposed_values",
            postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "reviewed_by_admin_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "review_note",
            sa.Text(),
            nullable=True,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="ck_user_profile_reviews_status",
        ),
    )

    op.create_index(
        "ix_user_profile_reviews_user_id",
        "user_profile_reviews",
        ["user_id"],
    )

    op.create_index(
        "uq_user_profile_reviews_one_pending_per_user",
        "user_profile_reviews",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_user_profile_reviews_one_pending_per_user",
        table_name="user_profile_reviews",
    )

    op.drop_index(
        "ix_user_profile_reviews_user_id",
        table_name="user_profile_reviews",
    )

    op.drop_table("user_profile_reviews")

    op.drop_constraint(
        "ck_users_profile_review_status",
        "users",
        type_="check",
    )

    op.drop_column("users", "profile_review_status")