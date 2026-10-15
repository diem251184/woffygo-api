from datetime import datetime
from decimal import Decimal
import enum
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geography

from app.core.database import Base


class ServiceType(str, enum.Enum):
    WALK = "WALK"
    TRANSPORT = "TRANSPORT"
    DAYCARE = "DAYCARE"


class BookingStatus(str, enum.Enum):
    REQUESTED = "REQUESTED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    service_type: Mapped[ServiceType] = mapped_column(
        SAEnum(ServiceType, name="service_type_enum"),
        default=ServiceType.WALK,
        nullable=False,
    )
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[BookingStatus] = mapped_column(
        SAEnum(BookingStatus, name="booking_status_enum"),
        default=BookingStatus.REQUESTED,
        nullable=False,
        index=True,
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    pickup_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pickup_location: Mapped[str] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    price_total: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), nullable=False
    )
    platform_fee: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), nullable=False
    )
    provider_earnings: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), nullable=False
    )

    cancellation_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cancelled_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    owner = relationship("User", foreign_keys=[owner_id])
    provider = relationship("User", foreign_keys=[provider_id])
    cancelled_by = relationship("User", foreign_keys=[cancelled_by_id])

    booking_pets = relationship(
        "BookingPet",
        back_populates="booking",
        cascade="all, delete-orphan",
    )

    locations = relationship(
        "WalkLocation",
        primaryjoin="Booking.id == foreign(WalkLocation.walk_id)",
        back_populates="booking",
        cascade="all, delete-orphan",
        order_by="WalkLocation.recorded_at",
    )

    payments = relationship(
        "Payment",
        primaryjoin="Booking.id == foreign(Payment.booking_id)",
        back_populates="booking",
    )

    @property
    def pets(self):
        return [bp.pet for bp in self.booking_pets if bp.pet is not None]


class BookingPet(Base):
    __tablename__ = "booking_pets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pet_id: Mapped[int] = mapped_column(
        ForeignKey("pets.id", ondelete="CASCADE"), nullable=False, index=True
    )

    booking = relationship("Booking", back_populates="booking_pets")
    pet = relationship("Pet")
