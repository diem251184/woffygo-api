from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import (
    create_access_token,
    generate_reset_token,
    hash_password,
    hash_reset_token,
    verify_password,
)
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User, UserRole
from app.schemas.user import (
    ForgotPasswordRequest,
    PasswordResetResponse,
    ResetPasswordRequest,
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)
from app.schemas.device_token import DeviceTokenCreate
from app.models.device_token import DeviceToken
from app.services import account
from app.services import email as email_service


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con ese email",
        )

    if payload.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No se puede registrar un administrador publicamente",
        )

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        phone=payload.phone,
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> Token:
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contrasena incorrectos",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario desactivado",
        )

    token = create_access_token(user.id, {"role": user.role.value})
    return Token(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    if payload.phone is not None:
        current_user.phone = payload.phone
    db.commit()
    db.refresh(current_user)
    return current_user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Elimina la cuenta del usuario autenticado (anonimiza datos)."""
    account.delete_account(db, current_user)


@router.post("/device-token", status_code=status.HTTP_204_NO_CONTENT)
def register_device_token(
    payload: DeviceTokenCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Registra o actualiza el token de push del dispositivo actual."""
    existing = (
        db.query(DeviceToken)
        .filter(DeviceToken.token == payload.token)
        .first()
    )
    if existing is not None:
        existing.user_id = current_user.id
        existing.platform = payload.platform
        existing.is_active = True
    else:
        db.add(DeviceToken(
            user_id=current_user.id,
            token=payload.token,
            platform=payload.platform,
            is_active=True,
        ))
    db.commit()


@router.post("/forgot-password", response_model=PasswordResetResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
) -> PasswordResetResponse:
    """Solicita el reset de contrasena.

    Por seguridad SIEMPRE devuelve 200 (no revela si el email existe o no).
    Si el email existe, invalida tokens previos no usados, genera uno nuevo
    y envia un email con el link de reset.
    """
    user = db.query(User).filter(User.email == payload.email).first()

    if user is not None and user.is_active:
        # Invalidar tokens previos no usados (por si pidio varias veces)
        now = datetime.now(timezone.utc)
        (
            db.query(PasswordResetToken)
            .filter(PasswordResetToken.user_id == user.id)
            .filter(PasswordResetToken.used_at.is_(None))
            .update({PasswordResetToken.used_at: now}, synchronize_session=False)
        )

        # Generar token nuevo
        raw_token = generate_reset_token()
        token_hash = hash_reset_token(raw_token)
        expires_at = now + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_MINUTES)

        db.add(PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        ))
        db.commit()

        # Enviar email (no rompemos la request si falla el envio)
        email_service.send_password_reset_email(
            to=user.email,
            full_name=user.full_name,
            token=raw_token,
        )

    return PasswordResetResponse(
        message="Si el email esta registrado, te enviamos un link para restablecer la contrasena."
    )


@router.post("/reset-password", response_model=PasswordResetResponse)
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
) -> PasswordResetResponse:
    """Aplica el reset de contrasena con el token recibido por email."""
    token_hash = hash_reset_token(payload.token)

    row = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == token_hash)
        .first()
    )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token invalido o expirado",
        )

    now = datetime.now(timezone.utc)

    # Asegurar comparacion de datetimes timezone-aware
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if row.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este link ya fue usado",
        )

    if expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token expirado",
        )

    user = db.query(User).filter(User.id == row.user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario no encontrado",
        )

    # Actualizar password y marcar token como usado
    user.password_hash = hash_password(payload.new_password)
    row.used_at = now
    db.commit()

    return PasswordResetResponse(
        message="Contrasena actualizada. Ya podes iniciar sesion con la nueva."
    )