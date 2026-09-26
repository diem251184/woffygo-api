"""Servicio de envio de emails via Resend API.

Resend:
- Endpoint: https://api.resend.com/emails
- Auth: Bearer <RESEND_API_KEY>
- En sandbox: el "from" debe ser onboarding@resend.dev
  y solo se puede enviar al email de registro de la cuenta Resend.
  Cuando se compre un dominio propio, se cambia EMAIL_FROM en el .env
  y se puede enviar a cualquier direccion.
"""
import httpx

from app.core.config import settings


RESEND_API_URL = "https://api.resend.com/emails"


def send_email(to: str, subject: str, html: str, text: str | None = None) -> bool:
    """Envia un email via Resend. Devuelve True si salio OK, False si fallo."""
    if not settings.RESEND_API_KEY:
        print("[email] ERROR: RESEND_API_KEY no configurada")
        return False

    payload = {
        "from": settings.EMAIL_FROM,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                RESEND_API_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            if response.status_code >= 400:
                print(f"[email] ERROR {response.status_code}: {response.text}")
            response.raise_for_status()
            data = response.json()
            print(f"[email] Enviado OK a {to} (id={data.get('id')})")
            return True
    except Exception as e:
        print(f"[email] Error enviando a Resend: {e}")
        return False


def send_password_reset_email(to: str, full_name: str, token: str) -> bool:
    """Envia el email de recuperacion con el link para resetear la contrasena."""
    reset_link = f"{settings.FRONTEND_RESET_URL}?token={token}"
    minutos = settings.PASSWORD_RESET_TOKEN_MINUTES
    subject = "Woofy Go - Recuperar contrasena"

    # DEBUG: log del token para poder testear en desarrollo.
    # Comentar este print cuando el flujo este 100% verificado en produccion.
    print(f"[email] DEBUG token para {to}: {token}")

    html = f"""
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 560px; margin: 0 auto; padding: 24px; color: #1F2937;">
  <div style="background: #1B4332; color: #FFFFFF; padding: 20px; border-radius: 12px 12px 0 0; text-align: center;">
    <h1 style="margin: 0; font-size: 22px; letter-spacing: 0.5px;">Woofy Go</h1>
  </div>
  <div style="background: #FFFFFF; padding: 24px; border: 1px solid #E5E7EB; border-top: none; border-radius: 0 0 12px 12px;">
    <p style="font-size: 16px; margin-top: 0;">Hola {full_name},</p>
    <p style="font-size: 15px; line-height: 22px;">
      Recibimos una solicitud para restablecer tu contrasena en Woofy Go.
      Hace click en el boton de abajo para elegir una nueva.
    </p>
    <p style="text-align: center; margin: 28px 0;">
      <a href="{reset_link}" style="display: inline-block; background: #C9A961; color: #FFFFFF; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 700; font-size: 15px;">
        Restablecer contrasena
      </a>
    </p>
    <p style="font-size: 13px; color: #6B7280; line-height: 20px;">
      Si vos no pediste esto, podes ignorar este email. El link caduca en {minutos} minutos.
    </p>
    <p style="font-size: 12px; color: #9CA3AF; margin-top: 24px; border-top: 1px solid #E5E7EB; padding-top: 16px;">
      Si el boton no funciona, copia y pega este link en tu navegador:<br/>
      <span style="word-break: break-all;">{reset_link}</span>
    </p>
  </div>
  <p style="text-align: center; font-size: 11px; color: #9CA3AF; margin-top: 16px;">
    Woofy Go - Paseo de perros en tiempo real
  </p>
</div>
"""

    text = f"""Hola {full_name},

Recibimos una solicitud para restablecer tu contrasena en Woofy Go.

Abri este link para elegir una nueva:
{reset_link}

Si vos no pediste esto, ignora este email. El link caduca en {minutos} minutos.

- Woofy Go
"""

    return send_email(to, subject, html, text)