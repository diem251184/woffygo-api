from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AdminAction(Base):
    """Registro de acciones administrativas (auditoria)."""

    __tablename__ = "admin_actions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Snapshot del email del admin (por si el user se elimina)
    admin_email: Mapped[str] = mapped_column(String(255), nullable=False)

    # Tipo de accion: user_block, user_unblock, flag_clear, dispute_resolve
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Sobre que actuo: user, walk, payment
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Descripcion legible para el panel
    description: Mapped[str] = mapped_column(String(500), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    admin = relationship("User", foreign_keys=[admin_id])
