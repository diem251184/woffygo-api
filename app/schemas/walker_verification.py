from datetime import datetime
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

    # Datos complementarios del paseador para la vista de Admin
    user_full_name: str | None = None
    user_email: str | None = None
    user_phone: str | None = None


class WalkerVerificationStatusOut(BaseModel):
    has_verification: bool
    status: str | None
    rejection_reason: str | None


class RejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
