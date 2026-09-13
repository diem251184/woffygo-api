"""Filtro anti-fuga de datos de contacto para el chat de Woffy Go.

Detecta y censura telefonos, emails, redes sociales y ofuscaciones
comunes en el texto de un mensaje. NO bloquea el mensaje: lo guarda
con los datos sensibles reemplazados por [dato bloqueado].

Reglas:
- No censura precios ($2500), numeros de paseo ("paseo 123") ni fechas.
- Detecta ofuscaciones comunes ("arroba", "wsp", "ig", etc.).
- Devuelve el texto filtrado + un motivo del bloqueo.
"""
import re


BLOCK_LABEL = "[dato bloqueado]"

# --- Patrones ---

# Fechas comunes (dd/mm/yyyy, dd-mm-yyyy, yyyy-mm-dd). Se usan para no
# confundirlas con telefonos.
DATE_PATTERN = re.compile(
    r"\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}|\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2})\b"
)

# Emails
EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)

# Telefonos: secuencias con 8-15 digitos, con separadores opcionales.
PHONE_PATTERN = re.compile(
    r"(?<![\d/])(\+?\d[\d\s\-\.\(\)]{6,}\d)(?![\d/])"
)

# Redes sociales / mensajeria: palabras clave (case-insensitive).
SOCIAL_PATTERN = re.compile(
    r"\b(whatsapp|whats\s*app|wsp|wasap|wasapp|telegram|instagram|insta|"
    r"ig|facebook|fb|messenger|tiktok|snapchat|discord|skype|zoom|"
    r"twitter|linkedin)\b",
    re.IGNORECASE,
)

# Ofuscaciones: "arroba", "punto com", "punto ar", "digito", etc.
OFUSCATION_PATTERN = re.compile(
    r"\b(arroba|at|punto\s*com|punto\s*ar|punto\s*net|punto\s*org|"
    r"digito\s+uno|digito\s+dos|digito\s+tres|digito\s+cuatro|"
    r"numero\s+uno|numero\s+dos|numero\s+tres|numero\s+cuatro|"
    r"cinco\s+cuatro|cero\s+nueve|uno\s+uno)\b",
    re.IGNORECASE,
)

# URLs genericas
URL_PATTERN = re.compile(
    r"\b(https?://|www\.)[^\s]+",
    re.IGNORECASE,
)

# Handles de redes sociales: @usuario o #usuario con al menos 4 caracteres.
# Excluye emails (ya capturados antes) y precios (#123 no matchea por length).
HANDLE_PATTERN = re.compile(
    r"(?<![\w@])[@#][A-Za-z0-9_.]{4,}(?![\w@])"
)


def _censor_phones(text: str) -> tuple[str, bool]:
    """Reemplaza telefonos sin tocar fechas."""
    # Primero protegemos las fechas temporalmente.
    date_placeholders: list[str] = []

    def protect_date(match: re.Match) -> str:
        idx = len(date_placeholders)
        date_placeholders.append(match.group(0))
        return f"__DATE_{idx}__"

    protected = DATE_PATTERN.sub(protect_date, text)

    def repl(match: re.Match) -> str:
        # Cuenta digitos reales (sin separadores).
        digits = re.sub(r"\D", "", match.group(0))
        if len(digits) < 8:
            return match.group(0)
        return BLOCK_LABEL

    new_text = PHONE_PATTERN.sub(repl, protected)

    # Restaurar fechas
    for idx, original in enumerate(date_placeholders):
        new_text = new_text.replace(f"__DATE_{idx}__", original)

    return new_text, new_text != text


def filter_contact_info(text: str) -> tuple[str, bool, str | None]:
    """Devuelve (filtered_text, was_blocked, block_reason).

    block_reason es una cadena tipo "phone,email" o None si no se bloqueo nada.
    """
    if not text:
        return text, False, None

    reasons: list[str] = []
    filtered = text

    # Emails primero (porque los telefonos podrian matchear dentro)
    new_filtered, email_changed = EMAIL_PATTERN.subn(BLOCK_LABEL, filtered)
    if email_changed:
        reasons.append("email")
        filtered = new_filtered

    # URLs
    new_filtered, url_changed = URL_PATTERN.subn(BLOCK_LABEL, filtered)
    if url_changed:
        reasons.append("url")
        filtered = new_filtered

    # Telefonos
    new_filtered, phone_changed = _censor_phones(filtered)
    if phone_changed:
        reasons.append("phone")
        filtered = new_filtered

    # Handles tipo @usuario o #usuario
    new_filtered, handle_changed = HANDLE_PATTERN.subn(BLOCK_LABEL, filtered)
    if handle_changed:
        reasons.append("handle")
        filtered = new_filtered

    # Redes sociales
    new_filtered, social_changed = SOCIAL_PATTERN.subn(BLOCK_LABEL, filtered)
    if social_changed:
        reasons.append("social")
        filtered = new_filtered

    # Ofuscaciones
    new_filtered, ofus_changed = OFUSCATION_PATTERN.subn(BLOCK_LABEL, filtered)
    if ofus_changed:
        reasons.append("ofuscated")
        filtered = new_filtered

    if not reasons:
        return text, False, None

    return filtered, True, ",".join(reasons)