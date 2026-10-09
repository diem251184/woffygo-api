import enum
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class WalkerVerificationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class WalkerVerification(Base):
    __tablename__ = "walker_verifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    dni_front_url: Mapped[str] = mapped_column(String(500), nullable=False)
    dni_back_url: Mapped[str] = mapped_column(String(500), nullable=False)
    selfie_url: Mapped[str] = mapped_column(String(500), nullable=False)

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