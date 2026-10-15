from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.payment import PaymentStatus


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_id: int | None = None
    walk_id: int | None = None
    payer_id: int
    amount: Decimal
    platform_fee: Decimal
    walker_earnings: Decimal
    status: PaymentStatus
    mp_preference_id: str | None = None
    mp_payment_id: str | None = None
    mp_status_detail: str | None = None
    init_point: str | None = None
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None = None
    payment_release_deadline: datetime | None = None
    confirmed_by_owner_at: datetime | None = None
    dispute_opened_at: datetime | None = None
    dispute_reason: str | None = None
    released_at: datetime | None = None


class PaymentDisputeRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=500)


class PaymentResolveRequest(BaseModel):
    release_to_walker: bool
    resolution_note: str | None = Field(default=None, max_length=120)
