from fastapi import APIRouter, Depends, status, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from io import BytesIO
import warnings
from PIL import Image, UnidentifiedImageError

from app.core.database import get_db
from app.core.deps import require_role
from app.models.user import User, UserRole
from app.models.pet import Pet
from app.schemas.pet import PetCreate, PetResponse, PetUpdate
from app.services import pets as pets_service
from app.services.cloudinary_service import upload_pet_image_to_cloudinary


router = APIRouter(prefix="/pets", tags=["pets"])

MAX_PET_PHOTO_BYTES = 8 * 1024 * 1024
MAX_PET_PHOTO_PIXELS = 20_000_000
ALLOWED_PET_PHOTO_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}


def valid_pet_image_signature(data: bytes, content_type: str) -> bool:
    if content_type == "image/jpeg":
        return data.startswith(bytes.fromhex("FFD8FF"))
    if content_type == "image/png":
        return data.startswith(bytes.fromhex("89504E470D0A1A0A"))
    if content_type == "image/webp":
        return (
            len(data) >= 12
            and data[:4] == b"RIFF"
            and data[8:12] == b"WEBP"
        )
    return False


@router.post("", response_model=PetResponse, status_code=status.HTTP_201_CREATED)
def create(
    payload: PetCreate,
    current_user: User = Depends(require_role(UserRole.OWNER)),
    db: Session = Depends(get_db),
):
    return pets_service.create_pet(db, current_user, payload)


@router.get("", response_model=list[PetResponse])
def list_mine(
    current_user: User = Depends(require_role(UserRole.OWNER)),
    db: Session = Depends(get_db),
):
    return pets_service.list_my_pets(db, current_user)


@router.get("/{pet_id}", response_model=PetResponse)
def get_one(
    pet_id: int,
    current_user: User = Depends(require_role(UserRole.OWNER)),
    db: Session = Depends(get_db),
):
    return pets_service.get_pet(db, pet_id, current_user)


@router.patch("/{pet_id}", response_model=PetResponse)
def update(
    pet_id: int,
    payload: PetUpdate,
    current_user: User = Depends(require_role(UserRole.OWNER)),
    db: Session = Depends(get_db),
):
    return pets_service.update_pet(db, pet_id, current_user, payload)


@router.delete("/{pet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    pet_id: int,
    current_user: User = Depends(require_role(UserRole.OWNER)),
    db: Session = Depends(get_db),
):
    pets_service.delete_pet(db, pet_id, current_user)


@router.post("/{pet_id}/photo", response_model=PetResponse)
@router.post("/{pet_id}/photo/", response_model=PetResponse)
async def upload_pet_photo(
    pet_id: int,
    photo: UploadFile = File(...),
    current_user: User = Depends(require_role(UserRole.OWNER)),
    db: Session = Depends(get_db),
):
    pet = db.query(Pet).filter(Pet.id == pet_id, Pet.owner_id == current_user.id).first()
    if not pet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mascota no encontrada o no pertenece al usuario",
        )

    content_type = (photo.content_type or "").lower().split(";")[0].strip()

    if content_type not in ALLOWED_PET_PHOTO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Formato no admitido. Usá JPEG, PNG o WebP.",
        )

    file_bytes = await photo.read(MAX_PET_PHOTO_BYTES + 1)

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo enviado está vacío",
        )

    if len(file_bytes) > MAX_PET_PHOTO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="La fotografía supera el máximo de 8 MB.",
        )

    if not valid_pet_image_signature(file_bytes, content_type):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="El contenido no coincide con un archivo de imagen admitido.",
        )

    formats = {
        "image/jpeg": "JPEG",
        "image/png": "PNG",
        "image/webp": "WEBP",
    }

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)

            with Image.open(BytesIO(file_bytes)) as image:
                if image.format != formats[content_type]:
                    raise ValueError("Formato real diferente del declarado")

                width, height = image.size
                if width <= 0 or height <= 0:
                    raise ValueError("Dimensiones de imagen invalidas")

                if width * height > MAX_PET_PHOTO_PIXELS:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="La imagen supera el maximo de 20 millones de pixeles.",
                    )

                image.verify()

            with Image.open(BytesIO(file_bytes)) as image:
                if image.format != formats[content_type]:
                    raise ValueError("Formato real diferente del declarado")
                image.load()

    except HTTPException:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="La fotografia no es una imagen valida o esta danada.",
        )

    try:
        secure_url = upload_pet_image_to_cloudinary(file_bytes, pet_id)
        pet.photo_url = secure_url
        db.add(pet)
        db.commit()
        db.refresh(pet)
        return pet
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error Cloudinary: {str(e)}",
        )
