"""Servicio de subida de imágenes a Cloudinary para KYC, Mascotas y Usuarios."""
import cloudinary
import cloudinary.uploader
from app.core.config import settings

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True,
)

from uuid import uuid4
def upload_pet_image_to_cloudinary(file_bytes: bytes, pet_id: int) -> str:
    """Sube la foto de una mascota a Cloudinary centrada y optimizada."""
    result = cloudinary.uploader.upload(
        file_bytes,
        folder=f"woffygo/pets/{pet_id}",
        transformation=[
            {"width": 600, "height": 600, "crop": "fill", "gravity": "auto"},
            {"quality": "auto", "fetch_format": "auto"}
        ],
    )
    return result["secure_url"]

def upload_user_avatar_to_cloudinary(file_bytes: bytes, user_id: int) -> str:
    """Sube la foto de perfil de un usuario centrada en su rostro y optimizada."""
    result = cloudinary.uploader.upload(
        file_bytes,
        folder=f"woffygo/users/{user_id}",
        transformation=[
            {"width": 500, "height": 500, "crop": "fill", "gravity": "face"},
            {"quality": "auto", "fetch_format": "auto"}
        ],
    )
    return result["secure_url"]

def upload_kyc_document(file_bytes: bytes, user_id: int, doc_type: str, register_attempt=None) -> str:
    """Sube un documento de identidad/KYC de paseador a Cloudinary de forma segura."""
    public_id = f"{doc_type}_{uuid4().hex}"
    if register_attempt is not None:
        register_attempt(f"woffygo/kyc/{user_id}/{public_id}")
    result = cloudinary.uploader.upload(
        file_bytes,
        folder=f"woffygo/kyc/{user_id}",
        public_id=public_id,
        overwrite=False,
        resource_type="image",
        type="authenticated",
        transformation=[{"quality": "auto", "fetch_format": "auto"}],
    )
    return result["secure_url"]

def delete_kyc_attempt(public_id: str, user_id: int) -> bool:
    """Elimina solamente un intento KYC nuevo con UUID valido.

    El llamador debe proporcionar exclusivamente identificadores
    registrados por su propia operacion fallida.
    """
    import re

    allowed_types = (
        "dni_front",
        "dni_back",
        "selfie",
        "license_front",
        "license_back",
        "vehicle_photo",
        "vehicle_cedula",
        "vehicle_insurance",
    )

    if type(user_id) is not int or user_id <= 0:
        raise ValueError("Usuario KYC invalido")

    if not isinstance(public_id, str):
        raise ValueError("Identificador KYC invalido")

    kinds = "|".join(re.escape(kind) for kind in allowed_types)
    expression = (
        rf"woffygo/kyc/{user_id}/"
        rf"(?:{kinds})_[0-9a-f]{{32}}"
    )

    if re.fullmatch(expression, public_id, flags=re.ASCII) is None:
        raise ValueError("Identificador KYC fuera del alcance permitido")

    result = cloudinary.uploader.destroy(
        public_id,
        resource_type="image",
        type="authenticated",
        invalidate=True,
    )

    if not isinstance(result, dict):
        return False

    return result.get("result") in ("ok", "not found")

def upload_pending_user_avatar(file_bytes: bytes, user_id: int) -> tuple[str, str]:
    """Create a separate pending avatar without overwriting approved images."""
    from uuid import uuid4

    if user_id <= 0 or not file_bytes:
        raise ValueError("Invalid pending avatar request")

    public_id = f"woffygo/users/{user_id}/pending/{uuid4().hex}"

    result = cloudinary.uploader.upload(
        file_bytes,
        public_id=public_id,
        overwrite=False,
        resource_type="image",
        transformation=[
            {"width": 500, "height": 500, "crop": "fill", "gravity": "face"},
            {"quality": "auto", "fetch_format": "auto"},
        ],
    )

    secure_url = result.get("secure_url")
    returned_id = result.get("public_id")

    if (not isinstance(secure_url, str)
            or not secure_url.startswith("https://")
            or returned_id != public_id):
        raise RuntimeError("Unexpected pending avatar upload response")

    return secure_url, public_id


def delete_pending_user_avatar(public_id: str, user_id: int) -> bool:
    """Allow removal only from the specified user's pending folder."""
    import re

    if not isinstance(public_id, str) or user_id <= 0:
        raise ValueError("Invalid pending avatar identifier")

    pattern = rf"woffygo/users/{user_id}/pending/[0-9a-f]{{32}}"

    if re.fullmatch(pattern, public_id) is None:
        raise ValueError("Refusing deletion outside pending avatar folder")

    response = cloudinary.uploader.destroy(
        public_id,
        resource_type="image",
        invalidate=True,
    )

    return response.get("result") in ("ok", "not found")

def pending_avatar_id_from_url(secure_url: str, user_id: int) -> str | None:
    """Recover only an exact pending Cloudinary asset ID for this user."""
    import re
    from urllib.parse import urlsplit

    if not isinstance(secure_url, str) or user_id <= 0:
        return None

    cloud_name = cloudinary.config().cloud_name
    if not isinstance(cloud_name, str) or not cloud_name:
        return None

    try:
        parsed = urlsplit(secure_url)
    except ValueError:
        return None

    if (
        parsed.scheme != "https"
        or parsed.hostname != "res.cloudinary.com"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.query
        or parsed.fragment
    ):
        return None

    pattern = (
        rf"/{re.escape(cloud_name)}/image/upload/"
        rf"(?:v[0-9]+/)?"
        rf"(woffygo/users/{user_id}/pending/[0-9a-f]{{32}})"
        rf"(?:\.[a-z0-9]+)?"
    )

    match = re.fullmatch(pattern, parsed.path)
    return match.group(1) if match else None
