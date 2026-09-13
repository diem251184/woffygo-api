from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geography

from app.core.database import Base


class WalkLocation(Base):
    __tablename__ = "walk_locations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    walk_id: Mapped[int] = mapped_column(
        ForeignKey("walks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    location: Mapped[str] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    accuracy_meters: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    speed_kmh: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    walk = relationship("Walk", back_populates="locations")
