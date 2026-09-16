from datetime import datetime
from decimal import Decimal
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
import enum

from app.core.database import Base


class WalkStatus(str, enum.Enum):
    PENDING = "pendiente"
    ACCEPTED = "aceptado"
    IN_PROGRESS = "en_proceso"
    COMPLETED = "completado"
    CANCELLED = "cancelado"


class Walk(Base):
    __tablename__ = "walks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    walker_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    status: Mapped[WalkStatus] = mapped_column(
        SAEnum(WalkStatus, name="walk_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=WalkStatus.PENDING,
        index=True,
    )
    pickup_location: Mapped[str] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    pickup_address: Mapped[str] = mapped_column(String(300), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    price_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    platform_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    walker_earnings: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
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

    flagged_for_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    flag_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    distance_meters: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    owner = relationship("User", foreign_keys=[owner_id])
    walker = relationship("User", foreign_keys=[walker_id])
    walk_pets = relationship(
        "WalkPet",
        back_populates="walk",
        cascade="all, delete-orphan",
    )
    locations = relationship(
        "WalkLocation",
        back_populates="walk",
        cascade="all, delete-orphan",
        order_by="WalkLocation.recorded_at",
    )

    @property
    def pet_ids(self) -> list[int]:
        return [wp.pet_id for wp in self.walk_pets]

    @property
    def pets(self) -> list:
        return [wp.pet for wp in self.walk_pets]

    @property
    def pickup_latitude(self) -> float | None:
        return getattr(self, "_pickup_latitude", None)

    @property
    def pickup_longitude(self) -> float | None:
        return getattr(self, "_pickup_longitude", None)

