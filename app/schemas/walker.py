from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class WalkerProfileCreate(BaseModel):
    bio: str | None = Field(default=None, max_length=500)
    search_radius_km: int = Field(default=5, ge=1, le=50)


class WalkerProfileUpdate(BaseModel):
    bio: str | None = Field(default=None, max_length=500)
    search_radius_km: int | None = Field(default=None, ge=1, le=50)


class WalkerLocationUpdate(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class WalkerOnlineToggle(BaseModel):
    is_online: bool


class WalkerProfileResponse(BaseModel):
    id: int
    user_id: int
    bio: str | None
    hourly_rate: Decimal
    search_radius_km: int
    is_online: bool
    rating_avg: Decimal
    total_walks: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WalkerNearbyResult(BaseModel):
    user_id: int
    full_name: str
    avatar_url: Optional[str] = None | None
    rating_avg: float
    total_walks: int
    hourly_rate: float
    distance_km: float