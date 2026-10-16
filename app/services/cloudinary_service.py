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
