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


class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"

    __table_args__ = (
        UniqueConstraint(
            "attempt_key",
            name="uq_payment_attempts_attempt_key",
        ),
        UniqueConstraint(
            "mp_preference_id",
            name="uq_payment_attempts_mp_preference",
        ),
        UniqueConstraint(
            "mp_payment_id",
            name="uq_payment_attempts_mp_payment",
        ),
        CheckConstraint(
            "amount > 0",
            name="ck_payment_attempts_amount_positive",
        ),
        Index(
            "ix_payment_attempts_payment_created",
            "payment_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )

    payment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("payments.id", ondelete="RESTRICT"),
        nullable=False,
    )

    attempt_key: Mapped[str] = mapped_column(
        String(64), nullable=False
    )

    mp_preference_id: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )

    mp_payment_id: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="created",
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )

    currency: Mapped[str] = mapped_column(
        String(3), nullable=False
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
