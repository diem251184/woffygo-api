from datetime import datetime
import enum
from sqlalchemy import String, DateTime, ForeignKey, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geography

from app.core.database import Base


class SafetyCategory(str, enum.Enum):
    STRAY_DOGS = "perros_sueltos"
    AGGRESSIVE_DOG = "perro_agresivo"
    POOR_LIGHTING = "zona_oscura"
    DANGEROUS_ZONE = "zona_peligrosa"
    OBSTACLE = "obstaculo_calle"
    OTHER = "otro"


class SafetyReport(Base):
    __tablename__ = "safety_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reporter_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Soporta tanto walk_id histórico como nuevo booking_id
    walk_id: Mapped[int | None] = mapped_column(
        ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    category: Mapped[SafetyCategory] = mapped_column(
        SAEnum(SafetyCategory, name="safety_category", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    location: Mapped[str] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    reporter = relationship("User")
    booking = relationship("Booking")
