from decimal import Decimal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    MERCADOPAGO_ACCESS_TOKEN: str = ""
    MERCADOPAGO_PUBLIC_KEY: str = ""
    MERCADOPAGO_WEBHOOK_SECRET: str = ""

    # Rango de tarifas por hora para paseadores
    MIN_HOURLY_RATE: Decimal = Decimal("2500.00")
    MAX_HOURLY_RATE: Decimal = Decimal("3500.00")

    PUBLIC_BASE_URL: str = "https://woffygo-api.onrender.com"

    # Recuperacion de contrasena (Resend)
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "onboarding@resend.dev"
    FRONTEND_RESET_URL: str = "woffygo://reset-password"
    PASSWORD_RESET_TOKEN_MINUTES: int = 30

    @field_validator("MAX_HOURLY_RATE")
    @classmethod
    def max_must_be_greater_than_min(cls, v: Decimal, info) -> Decimal:
        min_rate = info.data.get("MIN_HOURLY_RATE")
        if min_rate is not None and v < min_rate:
            raise ValueError("MAX_HOURLY_RATE debe ser >= MIN_HOURLY_RATE")
        return v


settings = Settings()