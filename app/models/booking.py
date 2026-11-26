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
from sqlalchemy.orm import Mapped, mapped_column, relationship, column_property
from geoalchemy2 import Geography
from geoalchemy2.shape import to_shape

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
    pickup_location: Mapped[str] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    pickup_address: Mapped[str] = mapped_column(String(255), nullable=False)
    dropoff_location: Mapped[str | None] = mapped_column(
        Geography(
            geometry_type="POINT",
            srid=4326,
            spatial_index=False,
        ),
        nullable=True,
    )
    dropoff_address: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)

    # Duracion vial estimada por el servidor.
    # NULL identifica reservas sin estimacion acreditada.
    estimated_transport_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    price_total: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), nullable=False
    )
    platform_fee: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), nullable=False
    )
    provider_earnings: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), nullable=False
    )

    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cancelled_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    scheduled_pickup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    flagged_for_review: Mapped[bool] = mapped_column(
        Boolean, server_default=func.false(), default=False, nullable=False
    )
    flag_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    distance_meters: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    # Relaciones
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

    @property
    def pickup_latitude(self) -> float | None:
        if hasattr(self, "_pickup_latitude") and self._pickup_latitude is not None:
            return self._pickup_latitude
        try:
            pt = to_shape(self.pickup_location)
            return float(pt.y)
        except Exception:
            return None

    @property
    def pickup_longitude(self) -> float | None:
        if hasattr(self, "_pickup_longitude") and self._pickup_longitude is not None:
            return self._pickup_longitude
        try:
            pt = to_shape(self.pickup_location)
            return float(pt.x)
        except Exception:
            return None

    @property
    def dropoff_latitude(self) -> float | None:
        if self.dropoff_location is None:
            return None
        point = to_shape(self.dropoff_location)
        return float(point.y)

    @property
    def dropoff_longitude(self) -> float | None:
        if self.dropoff_location is None:
            return None
        point = to_shape(self.dropoff_location)
        return float(point.x)

    @property
    def current_distance_meters(self) -> Decimal | None:
        # Preserve the existing behavior for non-transport services.
        if self.service_type != ServiceType.TRANSPORT:
            return self.distance_meters

        if self.started_at is None:
            return None

        from sqlalchemy import text
        from sqlalchemy.orm import object_session

        db = object_session(self)

        if db is None or self.id is None:
            return None

        # Never use the quoted road distance as traveled distance.
        # Calculate only from GPS samples recorded during this booking.
        sql = text("""
            WITH ordered_points AS (
                SELECT
                    id,
                    location,
                    recorded_at,
                    accuracy_meters,
                    speed_kmh,
                    LAG(location) OVER w AS previous_location,
                    LAG(recorded_at) OVER w AS previous_time,
                    LAG(accuracy_meters) OVER w AS previous_accuracy,
                    LAG(speed_kmh) OVER w AS previous_speed
                FROM walk_locations
                WHERE walk_id = :booking_id
                  AND recorded_at >= :started_at
                  AND (
                      CAST(:ended_at AS timestamptz) IS NULL
                      OR recorded_at <= CAST(:ended_at AS timestamptz)
                  )
                WINDOW w AS (
                    ORDER BY recorded_at, id
                )
            ),
            valid_pairs AS (
                SELECT
                    ST_Distance(
                        CAST(location AS geography),
                        CAST(previous_location AS geography)
                    ) AS segment_m,
                    EXTRACT(
                        EPOCH FROM (recorded_at - previous_time)
                    ) AS segment_s,
                    GREATEST(
                        5.0,
                        accuracy_meters,
                        previous_accuracy
                    ) AS noise_threshold
                FROM ordered_points
                WHERE previous_location IS NOT NULL
                  AND accuracy_meters BETWEEN 0 AND 50
                  AND previous_accuracy BETWEEN 0 AND 50
                  AND (
                      speed_kmh IS NULL
                      OR speed_kmh BETWEEN 0 AND 160
                  )
                  AND (
                      previous_speed IS NULL
                      OR previous_speed BETWEEN 0 AND 160
                  )
            ),
            credible_segments AS (
                SELECT
                    segment_m,
                    noise_threshold
                FROM valid_pairs
                WHERE segment_s > 0
                  AND segment_s <= 60
                  AND segment_m >= 0
                  AND segment_m * 3.6
                      <= segment_s * 160
            )
            SELECT
                CASE
                    WHEN COUNT(*) = 0 THEN NULL
                    ELSE SUM(
                        CASE
                            WHEN segment_m <= noise_threshold
                                THEN 0
                            ELSE segment_m
                        END
                    )
                END
            FROM credible_segments
        """)

        ended_at = self.finished_at or self.cancelled_at

        with db.no_autoflush:
            distance = db.execute(
                sql,
                {
                    "booking_id": self.id,
                    "started_at": self.started_at,
                    "ended_at": ended_at,
                },
            ).scalar_one()

        if distance is None:
            return None

        value = Decimal(str(distance))

        if not value.is_finite() or value < 0:
            return None

        return value.quantize(Decimal("0.01"))


from sqlalchemy.dialects.postgresql import JSONB


class BookingPet(Base):
    __tablename__ = "booking_pets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pet_id: Mapped[int] = mapped_column(
        ForeignKey("pets.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Declaraciones historicas al solicitar el servicio.
    # NULL identifica reservas anteriores sin evidencia historica.
    conditions_snapshot: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    booking = relationship("Booking", back_populates="booking_pets")
    pet = relationship("Pet", back_populates="booking_associations")
