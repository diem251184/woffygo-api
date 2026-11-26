from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TransportDeliveryCredential(Base):
    __tablename__ = "transport_delivery_credentials"

    __table_args__ = (
        CheckConstraint(
            "owner_received_at IS NULL OR "
            "(used_at IS NOT NULL "
            "AND invalidated_at IS NULL "
            "AND owner_received_at >= used_at)",
            name="ck_delivery_owner_receipt",
        ),
        CheckConstraint(
            "failed_attempts >= 0",
            name="ck_delivery_attempts_nonnegative",
        ),
        CheckConstraint(
            "key_version > 0",
            name="ck_delivery_key_version_positive",
        ),
        CheckConstraint(
            "char_length(pin_verifier) = 64",
            name="ck_delivery_verifier_length",
        ),
        CheckConstraint(
            "char_length(generation_nonce) = 64",
            name="ck_delivery_nonce_length",
        ),
        CheckConstraint(
            "used_at IS NULL OR used_at >= created_at",
            name="ck_delivery_used_after_creation",
        ),
        CheckConstraint(
            "invalidated_at IS NULL "
            "OR invalidated_at >= created_at",
            name="ck_delivery_invalidated_after_creation",
        ),
    )

    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"),
        primary_key=True,
    )

    pin_verifier: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    generation_nonce: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    key_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    failed_attempts: Mapped[int] = mapped_column(
        Integer,
        server_default=text("0"),
        default=0,
        nullable=False,
    )

    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    invalidated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    owner_received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
