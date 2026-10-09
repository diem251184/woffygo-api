"""Servicio de subida de imagenes a Cloudinary para KYC de walkers."""
import cloudinary
import cloudinary.uploader

from app.core.config import settings


cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True,
)


ALLOWED_MIME = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
MAX_SIZE_BYTES = 8 * 1024 * 1024  # 8 MB
MAX_SIZE_MB = MAX_SIZE_BYTES // 1024 // 1024


def upload_kyc_image(
    file_bytes: bytes,
    content_type: str | None,
    user_id: int,
    kind: str,
) -> str:
    """Sube una imagen de KYC a Cloudinary y devuelve la URL segura.

    kind: "dni_front" | "dni_back" | "selfie"
    """
    if content_type is None:
        raise ValueError("Falta el content-type del archivo")

    ct = content_type.lower().strip()
    if ct not in ALLOWED_MIME:
        raise ValueError(
            f"Formato no permitido: {content_type}. Usa JPG, PNG o WebP."
        )

    if len(file_bytes) == 0:
        raise ValueError("El archivo esta vacio")

    if len(file_bytes) > MAX_SIZE_BYTES:
        raise ValueError(f"El archivo supera el limite de {MAX_SIZE_MB} MB")

    result = cloudinary.uploader.upload(
        file_bytes,
        folder=f"woffygo/kyc/{user_id}",
        public_id=f"{kind}_{user_id}",
        overwrite=True,
        resource_type="image",
        transformation=[
            {"width": 1600, "height": 1600, "crop": "limit"},
            {"quality": "auto:good"},
        ],
    )
    return result["secure_url"]