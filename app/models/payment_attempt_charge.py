from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PaymentAttemptCharge(Base):
    __tablename__ = "payment_attempt_charges"

    __table_args__ = (
        UniqueConstraint(
            "mp_payment_id",
            name="uq_payment_attempt_charges_mp_payment_id",
        ),
        CheckConstraint(
            "amount IS NULL OR amount >= 0",
            name="ck_payment_attempt_charges_amount",
        ),
        Index(
            "ix_payment_attempt_charges_attempt_created",
            "attempt_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    attempt_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("payment_attempts.id", ondelete="RESTRICT"),
        nullable=False,
    )

    mp_payment_id: Mapped[str] = mapped_column(
        String(120), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(32), nullable=False
    )

    amount: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )

    currency: Mapped[str | None] = mapped_column(
        String(3), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
