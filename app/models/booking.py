from datetime import datetime
from decimal import Decimal
import enum
from sqlalchemy import (
    String,
    DateTime,
    Numeric,
    ForeignKey,
    Integer,
    Boolean,
    Enum as SAEnum,
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
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    provider_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    service_type: Mapped[ServiceType] = mapped_column(
        SAEnum(ServiceType, name="service_type_enum"),
        nullable=False,
        default=ServiceType.WALK,
        index=True,
    )
    status: Mapped[BookingStatus] = mapped_column(
        SAEnum(BookingStatus, name="booking_status_enum"),
        nullable=False,
        default=BookingStatus.REQUESTED,
        index=True,
    )

    pickup_location: Mapped[str] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    pickup_address: Mapped[str] = mapped_column(String(300), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)

    price_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    platform_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    provider_earnings: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)

    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)

    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    flagged_for_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    flag_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    distance_meters: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    owner = relationship("User", foreign_keys=[owner_id])
    provider = relationship("User", foreign_keys=[provider_id])
    booking_pets = relationship(
        "BookingPet",
        back_populates="booking",
        cascade="all, delete-orphan",
    )
    locations = relationship(
        "WalkLocation",
        back_populates="booking",
        cascade="all, delete-orphan",
        order_by="WalkLocation.recorded_at",
    )

    @property
    def pet_ids(self) -> list[int]:
        return [bp.pet_id for bp in self.booking_pets]

    @property
    def pets(self) -> list:
        return [bp.pet for bp in self.booking_pets]

    @property
    def pickup_latitude(self) -> float | None:
        return getattr(self, "_pickup_latitude", None)

    @property
    def pickup_longitude(self) -> float | None:
        return getattr(self, "_pickup_longitude", None)

    @property
    def current_distance_meters(self) -> Decimal | None:
        return getattr(self, "_current_distance_meters", None)


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
