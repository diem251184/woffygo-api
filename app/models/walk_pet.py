from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class WalkPet(Base):
    __tablename__ = "walk_pets"
    __table_args__ = (
        UniqueConstraint("walk_id", "pet_id", name="uq_walk_pets_walk_pet"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    walk_id: Mapped[int] = mapped_column(
        ForeignKey("walks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pet_id: Mapped[int] = mapped_column(
        ForeignKey("pets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    walk = relationship("Walk", back_populates="walk_pets")
    pet = relationship("Pet", back_populates="walk_pets")