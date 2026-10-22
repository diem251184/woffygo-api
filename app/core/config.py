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

    # Cloudinary (KYC de walkers)
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    MAPBOX_ACCESS_TOKEN: str = ""

    PUBLIC_BASE_URL: str = "https://woffygo-api.onrender.com"

    # Recuperacion de contrasena (Resend)
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "onboarding@resend.dev"
    FRONTEND_RESET_URL: str = "woffygo://reset-password"
    PASSWORD_RESET_TOKEN_MINUTES: int = 30

    # Secreto compartido para que un cron externo pueda pegarle a endpoints
    # internos (ej: /payments/admin/release-expired) sin necesidad de loguearse
    # como admin. Si queda vacio, la via cron queda deshabilitada.
    CRON_SECRET: str = ""

    # Info de version de la app movil (para el cartel de "nueva version")
    # Cada vez que publiques una APK nueva, actualiza LATEST_APP_VERSION aca
    # en Render y la app avisa a los usuarios que hay actualizacion disponible.
    LATEST_APP_VERSION: str = "1.0.0"
    MIN_SUPPORTED_APP_VERSION: str = "1.0.0"
    APP_DOWNLOAD_URL: str = "https://woffygo-api.onrender.com/descargar"
    APP_RELEASE_NOTES: str = ""


settings = Settings()