from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Boolean, DateTime, Numeric, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geography

from app.core.database import Base


class WalkerProfile(Base):
    __tablename__ = "walker_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    bio: Mapped[str | None] = mapped_column(String(500), nullable=True)
    hourly_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    search_radius_km: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    is_online: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    current_location: Mapped[str | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=True
    )
    last_location_update: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rating_avg: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False, default=0)
    total_walks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user = relationship("User", back_populates="walker_profile")
