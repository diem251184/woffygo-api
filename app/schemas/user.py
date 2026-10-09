from datetime import datetime, date
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
from app.models.user import UserRole


def parse_flexible_date(v) -> date | None:
    if not v:
        return None
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        v = v.strip()
        if not v:
            return None
        # Probar DD/MM/YYYY o DD-MM-YYYY
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(v, fmt).date()
            except ValueError:
                pass
        raise ValueError("Formato de fecha inválido. Usá DD/MM/AAAA (ej: 14/01/1985)")
    return None


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=6, max_length=30)
    dni_number: str | None = None
    address: str | None = None
    birth_date: date | None = None
    emergency_contact: str | None = None

    @field_validator("birth_date", mode="before")
    @classmethod
    def validate_birth_date(cls, v):
        return parse_flexible_date(v)


class UserCreate(UserBase):
    password: str = Field(min_length=6, max_length=72)
    role: UserRole = UserRole.OWNER


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: UserRole
    is_active: bool
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, min_length=6, max_length=30)
    dni_number: str | None = None
    address: str | None = None
    birth_date: date | None = None
    emergency_contact: str | None = None

    @field_validator("birth_date", mode="before")
    @classmethod
    def validate_update_birth_date(cls, v):
        return parse_flexible_date(v)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    exp: int
    role: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=512)
    new_password: str = Field(min_length=6, max_length=72)


class PasswordResetResponse(BaseModel):
    message: str
