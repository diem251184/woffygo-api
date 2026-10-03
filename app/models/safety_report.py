from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, ForeignKey, Integer, func, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.core.database import Base


class SafetyCategory(str, enum.Enum):
    DANGER = "danger"                 # ⚠️ Peligro
    LOW_VISIBILITY = "low_visibility" # 🌑 Poca visibilidad
    OTHER = "other"                   # ❓ Otro


class SafetyReport(Base):
    """Reporte de seguridad tipo Waze, asociado a un paseo."""

    __tablename__ = "safety_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    reporter_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reporter_role: Mapped[str] = mapped_column(String(20), nullable=False)

    walk_id: Mapped[int | None] = mapped_column(
        ForeignKey("walks.id", ondelete="SET NULL"), nullable=True, index=True
    )

    category: Mapped[SafetyCategory] = mapped_column(
        SAEnum(SafetyCategory, name="safety_category",
               values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Coordenadas (guardadas directo, no PostGIS para simplificar)
    latitude: Mapped[float] = mapped_column(nullable=False)
    longitude: Mapped[float] = mapped_column(nullable=False)

    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    deleted_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    reporter = relationship("User")
    walk = relationship("Walk")
