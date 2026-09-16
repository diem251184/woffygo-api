from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.walk import WalkStatus
from app.schemas.pet import PetMinimal


MAX_PETS_PER_WALK = 3


class WalkCreate(BaseModel):
    pet_ids: list[int] = Field(min_length=1, max_length=MAX_PETS_PER_WALK)
    pickup_latitude: float = Field(ge=-90, le=90)
    pickup_longitude: float = Field(ge=-180, le=180)
    pickup_address: str = Field(min_length=5, max_length=300)
    duration_minutes: int = Field(default=60, ge=60, le=180)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("pet_ids")
    @classmethod
    def pet_ids_must_be_unique(cls, v: list[int]) -> list[int]:
        if len(set(v)) != len(v):
            raise ValueError("No se pueden repetir mascotas en un mismo paseo")
        return v


class WalkCancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


class WalkLocationCreate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_meters: float | None = Field(default=None, ge=0)
    speed_kmh: float | None = Field(default=None, ge=0)


class WalkLocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    walk_id: int
    accuracy_meters: Decimal | None
    speed_kmh: Decimal | None
    recorded_at: datetime


class WalkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    walker_id: int | None
    status: WalkStatus
    pickup_address: str
    duration_minutes: int
    price_total: Decimal
    platform_fee: Decimal
    walker_earnings: Decimal
    notes: str | None
    cancel_reason: str | None
    requested_at: datetime
    accepted_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime
    flagged_for_review: bool
    flag_reason: str | None
    distance_meters: Decimal | None
    pet_ids: list[int]
    pets: list[PetMinimal]

class WalkLocationDetail(BaseModel):
    """Ubicacion GPS con lat/lon extraidos, para el mapa en vivo."""

    id: int
    walk_id: int
    latitude: float
    longitude: float
    accuracy_meters: Decimal | None
    speed_kmh: Decimal | None
    recorded_at: datetime

