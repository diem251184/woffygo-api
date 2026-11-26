"""Persistent financial origin and TEST release protection."""

from alembic import op
import sqlalchemy as sa

revision = "cl145paymentorigin"
down_revision = "cl145transportduration"
branch_labels = None
depends_on = None


def upgrade():

    op.add_column(
        "payments",
        sa.Column(
            "financial_origin",
            sa.String(length=16),
            nullable=False,
            server_default="UNVERIFIED",
        ),
    )

    op.create_check_constraint(
        "ck_payments_financial_origin",
        "payments",
        "financial_origin IN ('TEST', 'REAL', 'UNVERIFIED')",
    )

    op.create_check_constraint(
        "ck_payments_test_not_released",
        "payments",
        "financial_origin <> 'TEST' OR "
        "(status <> 'liberado' AND released_at IS NULL)",
    )

    op.execute("""
        CREATE FUNCTION woffy_protect_test_payment_origin()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.financial_origin = 'TEST'
               AND NEW.financial_origin <> 'TEST' THEN
                RAISE EXCEPTION
                    'TEST payment origin cannot be changed'
                    USING ERRCODE = '23514';
            END IF;

            RETURN NEW;
        END;
        $$;
    """)

    op.execute("""
        CREATE TRIGGER trg_payments_protect_test_origin
        BEFORE UPDATE OF financial_origin ON payments
        FOR EACH ROW
        EXECUTE FUNCTION woffy_protect_test_payment_origin();
    """)


def downgrade():

    bind = op.get_bind()

    test_exists = bind.execute(
        sa.text(
            "SELECT EXISTS ("
            "SELECT 1 FROM payments "
            "WHERE financial_origin = 'TEST')"
        )
    ).scalar_one()

    if test_exists:
        raise RuntimeError(
            "Downgrade blocked: persistent TEST payments exist"
        )

    op.execute(
        "DROP TRIGGER trg_payments_protect_test_origin "
        "ON payments"
    )

    op.execute(
        "DROP FUNCTION woffy_protect_test_payment_origin()"
    )

    op.drop_constraint(
        "ck_payments_test_not_released",
        "payments",
        type_="check",
    )

    op.drop_constraint(
        "ck_payments_financial_origin",
        "payments",
        type_="check",
    )

    op.drop_column(
        "payments",
        "financial_origin",
    )
