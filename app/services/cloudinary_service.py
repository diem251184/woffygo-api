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
