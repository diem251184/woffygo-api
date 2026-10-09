from datetime import datetime, date
from pydantic import BaseModel, ConfigDict, Field


class WalkerVerificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    dni_front_url: str
    dni_back_url: str
    selfie_url: str
    status: str
    rejection_reason: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    # Datos extendidos del paseador (Uber style)
    user_full_name: str | None = None
    user_email: str | None = None
    user_phone: str | None = None
    user_dni_number: str | None = None
    user_address: str | None = None
    user_birth_date: date | None = None
    user_emergency_contact: str | None = None


class WalkerVerificationStatusOut(BaseModel):
    has_verification: bool
    status: str | None
    rejection_reason: str | None


class RejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
