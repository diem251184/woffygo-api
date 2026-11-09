"""Solicitudes persistentes de reembolso; no ejecuta devoluciones."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PaymentRefundRequest(Base):
    __tablename__ = "payment_refund_requests"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    mp_payment_id: Mapped[str] = mapped_column(
        String(120), nullable=False, unique=True
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(36), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'prepared'"),
    )
    mp_refund_id: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )
    response_http_status: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    response_status: Mapped[str | None] = mapped_column(
        String(80), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
