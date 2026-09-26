from datetime import datetime, timedelta, timezone
from typing import Any
import hashlib
import secrets

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str | int, extra: dict[str, Any] | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {"sub": str(subject), "exp": expire}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


def generate_reset_token() -> str:
    """Genera un token random URL-safe de 32 bytes (43 caracteres aprox)."""
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    """Devuelve el SHA-256 hex del token. Es lo que guardamos en la DB."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()