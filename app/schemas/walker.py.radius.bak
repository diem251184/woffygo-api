from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings


class WalkerProfileCreate(BaseModel):
    bio: str | None = Field(default=None, max_length=500)
    hourly_rate: Decimal = Field(default=Decimal("0"), ge=0)
    search_radius_km: int = Field(default=5, ge=1, le=50)

    @field_validator("hourly_rate")
    @classmethod
    def rate_within_range(cls, v: Decimal) -> Decimal:
        if v < settings.MIN_HOURLY_RATE:
            raise ValueError(
                f"La tarifa minima es ${settings.MIN_HOURLY_RATE}/hora"
            )
        if v > settings.MAX_HOURLY_RATE:
            raise ValueError(
                f"La tarifa maxima es ${settings.MAX_HOURLY_RATE}/hora"
            )
        return v


class WalkerProfileUpdate(BaseModel):
    bio: str | None = Field(default=None, max_length=500)
    hourly_rate: Decimal | None = Field(default=None, ge=0)
    search_radius_km: int | None = Field(default=None, ge=1, le=50)

    @field_validator("hourly_rate")
    @classmethod
    def rate_within_range(cls, v: Decimal | None) -> Decimal | None:
        if v is None:
            return v
        if v < settings.MIN_HOURLY_RATE:
            raise ValueError(
                f"La tarifa minima es ${settings.MIN_HOURLY_RATE}/hora"
            )
        if v > settings.MAX_HOURLY_RATE:
            raise ValueError(
                f"La tarifa maxima es ${settings.MAX_HOURLY_RATE}/hora"
            )
        return v


class WalkerProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    bio: str | None
    hourly_rate: Decimal
    search_radius_km: int
    is_online: bool
    rating_avg: Decimal
    total_walks: int
    last_location_update: datetime | None
    created_at: datetime


class WalkerLocationUpdate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class WalkerNearbyResult(BaseModel):
    walker_id: int
    user_id: int
    full_name: str
    hourly_rate: Decimal
    rating_avg: Decimal
    total_walks: int
    distance_km: float
    latitude: float
    longitude: float


class WalkerOnlineToggle(BaseModel):
    is_online: bool