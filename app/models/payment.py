from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    String,
    DateTime,
    Numeric,
    ForeignKey,
    Enum as SAEnum,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.core.database import Base


class PaymentStatus(str, enum.Enum):
    PENDING = "pendiente"
    APPROVED = "aprobado"
    REJECTED = "rechazado"
    REFUNDED = "reembolsado"
    CANCELLED = "cancelado"
    RELEASED = "liberado"
    DISPUTED = "en_disputa"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    walk_id: Mapped[int] = mapped_column(
        ForeignKey("walks.id", ondelete="CASCADE"), nullable=False, index=True, unique=True
    )
    payer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    platform_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    walker_earnings: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(PaymentStatus, name="payment_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=PaymentStatus.PENDING,
        index=True,
    )
    mp_preference_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    mp_payment_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    mp_status_detail: Mapped[str | None] = mapped_column(String(120), nullable=True)
    init_point: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Escrow bilateral
    payment_release_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    confirmed_by_owner_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dispute_opened_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dispute_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    walk = relationship("Walk")
    payer = relationship("User", foreign_keys=[payer_id])