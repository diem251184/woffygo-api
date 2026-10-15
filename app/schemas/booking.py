from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from app.models.booking import ServiceType, BookingStatus
from app.schemas.pet import PetResponse


class BookingCreate(BaseModel):
    service_type: ServiceType = ServiceType.WALK
    pet_ids: list[int] = Field(..., min_items=1, max_items=3)
    pickup_latitude: float
    pickup_longitude: float
    pickup_address: str
    duration_minutes: int = Field(default=30, ge=15, le=180)
    notes: str | None = None


class BookingQuoteRequest(BaseModel):
    service_type: ServiceType = ServiceType.WALK
    provider_id: int
    duration_minutes: int = 30
    num_pets: int = 1


class BookingQuoteResponse(BaseModel):
    price_total: Decimal
    platform_fee: Decimal
    provider_earnings: Decimal
    currency: str = "ARS"


class BookingStatusUpdateRequest(BaseModel):
    status: BookingStatus
    reason: str | None = None


class BookingResponse(BaseModel):
    id: int
    owner_id: int
    provider_id: int | None
    service_type: ServiceType
    status: BookingStatus
    pickup_address: str
    duration_minutes: int
    price_total: Decimal
    platform_fee: Decimal
    provider_earnings: Decimal
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
    pets: list[PetResponse] = []
    pickup_latitude: float | None = None
    pickup_longitude: float | None = None
    current_distance_meters: Decimal | None = None

    class Config:
        from_attributes = True


class BookingLocationCreate(BaseModel):
    latitude: float
    longitude: float
    accuracy_meters: float | None = None
    speed_kmh: float | None = None


class BookingLocationDetail(BaseModel):
    id: int
    booking_id: int
    latitude: float
    longitude: float
    accuracy_meters: float | None
    speed_kmh: float | None
    recorded_at: datetime

    class Config:
        from_attributes = True
