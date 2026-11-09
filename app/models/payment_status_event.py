"""Historial interno de transiciones de estados de pagos.

No representa un libro contable ni confirma movimientos
externos de dinero. Los eventos se registraran en pasos
posteriores, dentro de la transaccion financiera.
"""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PaymentStatusEvent(Base):
    __tablename__ = "payment_status_events"

    __table_args__ = (
        UniqueConstraint(
            "payment_id",
            "event_key",
            name="uq_payment_status_events_payment_key",
        ),
        Index(
            "ix_payment_status_events_payment_created",
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

    previous_status: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )

    new_status: Mapped[str] = mapped_column(
        String(32), nullable=False
    )

    event_source: Mapped[str] = mapped_column(
        String(32), nullable=False
    )

    event_key: Mapped[str | None] = mapped_column(
        String(160), nullable=True
    )

    mp_payment_id: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )
