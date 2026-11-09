import enum
from datetime import datetime, date

from sqlalchemy import (
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    String,
    Text,
    Date,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class WalkerVerificationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class DocumentStatus(str, enum.Enum):
    MISSING = "missing"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class WalkerVerification(Base):
    __tablename__ = "walker_verifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # --- BLOQUE IDENTIDAD ---
    identity_status: Mapped[DocumentStatus] = mapped_column(
        SQLEnum(DocumentStatus, name="document_status", values_callable=lambda x: [e.value for e in x]), default=DocumentStatus.MISSING, nullable=False
    )
    dni_front_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dni_back_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    selfie_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    identity_rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- BLOQUE LICENCIA (Solo Pet Taxi) ---
    license_status: Mapped[DocumentStatus] = mapped_column(
        SQLEnum(DocumentStatus, name="document_status", values_callable=lambda x: [e.value for e in x]), default=DocumentStatus.MISSING, nullable=False
    )
    license_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    license_class: Mapped[str | None] = mapped_column(String(50), nullable=True)
    license_jurisdiction: Mapped[str | None] = mapped_column(String(100), nullable=True)
    license_expiration: Mapped[date | None] = mapped_column(Date, nullable=True)
    license_front_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    license_back_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    license_rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- BLOQUE VEHÍCULO (Solo Pet Taxi) ---
    vehicle_status: Mapped[DocumentStatus] = mapped_column(
        SQLEnum(DocumentStatus, name="document_status", values_callable=lambda x: [e.value for e in x]), default=DocumentStatus.MISSING, nullable=False
    )
    vehicle_plate: Mapped[str | None] = mapped_column(String(20), nullable=True)
    vehicle_brand: Mapped[str | None] = mapped_column(String(50), nullable=True)
    vehicle_model: Mapped[str | None] = mapped_column(String(50), nullable=True)
    vehicle_year: Mapped[int | None] = mapped_column(nullable=True)
    vehicle_photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    vehicle_cedula_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    vehicle_insurance_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    vehicle_inspection_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    vehicle_rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- ESTADO GLOBAL Y AUDITORÍA ---
    status: Mapped[WalkerVerificationStatus] = mapped_column(
        SQLEnum(WalkerVerificationStatus, name="walker_verification_status"),
        nullable=False,
        default=WalkerVerificationStatus.PENDING,
        index=True,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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

    user = relationship("User", foreign_keys=[user_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_admin_id])
