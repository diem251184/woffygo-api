from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Boolean, DateTime, Numeric, ForeignKey, Integer, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.booking import ServiceType


class ProviderService(Base):
    __tablename__ = "provider_services"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    service_type: Mapped[ServiceType] = mapped_column(
        SAEnum(ServiceType, name="service_type_enum"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    price_per_km: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    price_per_day: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    service_radius_km: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    provider = relationship("User")
