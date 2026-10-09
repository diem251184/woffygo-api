from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
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

# ---------------------------------------------------------------
# Reset redirect: pagina intermedia que convierte un link https
# en un deep link woffygo:// para que Gmail / navegadores lo acepten.
# ---------------------------------------------------------------

def _redirect_html(deep_link: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Woofy Go - Restablecer contrasena</title>
<style>
  body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #1B4332;
    color: #FFFFFF;
    display: flex;
    min-height: 100vh;
    align-items: center;
    justify-content: center;
    padding: 24px;
    box-sizing: border-box;
  }}
  .card {{
    background: #FFFFFF;
    color: #1F2937;
    border-radius: 16px;
    padding: 32px 24px;
    max-width: 420px;
    width: 100%;
    text-align: center;
    box-shadow: 0 10px 30px rgba(0,0,0,0.25);
  }}
  .logo {{
    font-size: 22px;
    font-weight: 800;
    color: #1B4332;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
  }}
  h1 {{
    font-size: 20px;
    margin: 16px 0 8px 0;
    color: #1F2937;
  }}
  p {{
    font-size: 14px;
    color: #6B7280;
    line-height: 21px;
    margin: 0 0 20px 0;
  }}
  .btn {{
    display: inline-block;
    background: #C9A961;
    color: #FFFFFF;
    padding: 14px 28px;
    border-radius: 10px;
    text-decoration: none;
    font-weight: 700;
    font-size: 15px;
    margin-top: 8px;
  }}
  .hint {{
    font-size: 12px;
    color: #9CA3AF;
    margin-top: 20px;
  }}
</style>
</head>
<body>
  <div class="card">
    <div class="logo">Woofy Go</div>
    <h1>Restablecer contrasena</h1>
    <p>Estamos abriendo la app para que puedas elegir una nueva contrasena...</p>
    <a class="btn" href="{deep_link}">Abrir Woofy Go</a>
    <p class="hint">Si no se abre sola, toc&aacute; el bot&oacute;n de arriba.</p>
  </div>
  <script>
    // Intento 1: abrir el deep link automaticamente
    window.location.href = "{deep_link}";
    // Intento 2: por si el navegador bloquea el primero
    setTimeout(function() {{
      window.location.href = "{deep_link}";
    }}, 300);
  </script>
</body>
</html>
"""


def _invalid_link_html() -> str:
    return """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Woofy Go - Link invalido</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         background: #1B4332; color: #FFFFFF; display: flex; min-height: 100vh;
         align-items: center; justify-content: center; padding: 24px; margin: 0; box-sizing: border-box; }
  .card { background: #FFFFFF; color: #1F2937; border-radius: 16px; padding: 32px 24px;
          max-width: 420px; width: 100%; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.25); }
  .logo { font-size: 22px; font-weight: 800; color: #1B4332; margin-bottom: 12px; }
  h1 { font-size: 20px; margin: 8px 0; color: #B91C1C; }
  p { font-size: 14px; color: #6B7280; line-height: 21px; margin: 0; }
</style>
</head>
<body>
  <div class="card">
    <div class="logo">Woofy Go</div>
    <h1>Link invalido</h1>
    <p>Este link no tiene un token valido. Pedi uno nuevo desde la pantalla de inicio de sesion.</p>
  </div>
</body>
</html>
"""


@router.get("/reset-redirect", response_class=HTMLResponse, include_in_schema=False)
def reset_redirect(token: str = "") -> HTMLResponse:
    """Pagina intermedia que convierte un link https en un deep link woffygo://.

    Necesario porque Gmail y los navegadores bloquean links con schemes custom.
    El usuario toca un link https normal, el backend devuelve un HTML que
    intenta abrir la app via el deep link woffygo://reset-password.
    """
    if not token or len(token) < 10:
        return HTMLResponse(content=_invalid_link_html(), status_code=400)

    deep_link = f"woffygo://reset-password?token={token}"
    return HTMLResponse(content=_redirect_html(deep_link))