from datetime import datetime
from sqlalchemy import (
    String,
    Text,
    DateTime,
    ForeignKey,
    Boolean,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    walk_id: Mapped[int] = mapped_column(
        ForeignKey("walks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    # Texto original tal como lo escribio el usuario
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # Texto con datos de contacto censurados (lo que ve el receptor)
    filtered_text: Mapped[str] = mapped_column(Text, nullable=False)

    # True si el filtro detecto y bloqueo algo
    was_blocked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )

    # Razon del bloqueo: "phone", "email", "social", "ofuscated"
    block_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    walk = relationship("Walk")
    sender = relationship("User", foreign_keys=[sender_id])