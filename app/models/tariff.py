from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Float, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

class TariffHistory(Base):
    __tablename__ = "tariff_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    service_type: Mapped[str] = mapped_column(String, index=True)
    base_price: Mapped[float] = mapped_column(Float)
    per_km_price: Mapped[float] = mapped_column(Float, nullable=True)
    extra_pet_price: Mapped[float] = mapped_column(Float, default=0.0)
    ipc_applied: Mapped[float] = mapped_column(Float, default=0.0)

    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    valid_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    approved_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)