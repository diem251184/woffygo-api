from datetime import datetime, date
from pydantic import BaseModel, ConfigDict, Field

class WalkerVerificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int

    # Identidad
    identity_status: str
    identity_rejection_reason: str | None = None
    dni_front_url: str | None = None
    dni_back_url: str | None = None
    selfie_url: str | None = None

    # Licencia
    license_status: str
    license_rejection_reason: str | None = None
    license_number: str | None = None
    license_class: str | None = None
    license_jurisdiction: str | None = None
    license_expiration: date | None = None
    license_front_url: str | None = None
    license_back_url: str | None = None

    # Vehiculo
    vehicle_status: str
    vehicle_rejection_reason: str | None = None
    vehicle_plate: str | None = None
    vehicle_brand: str | None = None
    vehicle_model: str | None = None
    vehicle_year: int | None = None
    vehicle_photo_url: str | None = None
    vehicle_cedula_url: str | None = None
    vehicle_insurance_url: str | None = None
    vehicle_inspection_url: str | None = None

    # Global y Auditoria
    status: str
    rejection_reason: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    # Datos del usuario (Uber style)
    user_full_name: str | None = None
    user_email: str | None = None
    user_phone: str | None = None
    user_dni_number: str | None = None
    user_address: str | None = None
    user_birth_date: date | None = None
    user_emergency_contact: str | None = None

class WalkerVerificationStatusOut(BaseModel):
    has_verification: bool
    status: str | None = None
    identity_status: str | None = None
    license_status: str | None = None
    vehicle_status: str | None = None
    rejection_reason: str | None = None

class RejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class WalkerVerificationAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    identity_status: str
    identity_rejection_reason: str | None = None
    license_status: str
    license_rejection_reason: str | None = None
    license_number: str | None = None
    license_class: str | None = None
    license_jurisdiction: str | None = None
    license_expiration: date | None = None
    vehicle_status: str
    vehicle_rejection_reason: str | None = None
    vehicle_plate: str | None = None
    vehicle_brand: str | None = None
    vehicle_model: str | None = None
    vehicle_year: int | None = None
    status: str
    rejection_reason: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    user_full_name: str | None = None
    user_email: str | None = None
    user_phone: str | None = None
    user_dni_number: str | None = None
    user_address: str | None = None
    user_birth_date: date | None = None
    user_emergency_contact: str | None = None
