from datetime import datetime, date
from pydantic import BaseModel, EmailStr, Field
from app.models.user import UserRole


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=6, max_length=30)
    role: UserRole


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)
    dni_number: str | None = None
    address: str | None = None
    birth_date: date | None = None
    emergency_contact: str | None = None


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, min_length=6, max_length=30)
    dni_number: str | None = None
    address: str | None = None
    birth_date: date | None = None
    emergency_contact: str | None = None
    profile_photo_url: str | None = None


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    phone: str
    role: UserRole
    profile_photo_url: str | None = None
    dni_number: str | None = None
    address: str | None = None
    birth_date: date | None = None
    emergency_contact: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
