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

# ---- CL143: documentos sanitarios privados de mascotas ----

from app.models.pet_health_document import PetHealthDocument
from app.services.pet_health_documents import (
    upload_pet_health_document as store_pet_health_document,
    delete_pet_health_document as remove_pet_health_document,
)


@router.get("/{pet_id}/health-documents")
def list_pet_health_documents(
    pet_id: int,
    current_user: User = Depends(require_role(UserRole.OWNER)),
    db: Session = Depends(get_db),
):
    pet = db.query(Pet).filter(
        Pet.id == pet_id,
        Pet.owner_id == current_user.id,
    ).first()

    if pet is None:
        raise HTTPException(status_code=404, detail="Mascota no encontrada")

    documents = (
        db.query(PetHealthDocument)
        .filter(PetHealthDocument.pet_id == pet.id)
        .order_by(PetHealthDocument.id.desc())
        .all()
    )

    return [
        {
            "id": item.id,
            "pet_id": item.pet_id,
            "content_type": item.content_type,
            "created_at": item.created_at,
        }
        for item in documents
    ]


@router.post("/{pet_id}/health-documents", status_code=201)
async def upload_pet_health_document_endpoint(
    pet_id: int,
    document: UploadFile = File(...),
    current_user: User = Depends(require_role(UserRole.OWNER)),
    db: Session = Depends(get_db),
):
    pet = db.query(Pet).filter(
        Pet.id == pet_id,
        Pet.owner_id == current_user.id,
    ).first()

    if pet is None:
        raise HTTPException(status_code=404, detail="Mascota no encontrada")

    content_type = (
        (document.content_type or "").lower().split(";")[0].strip()
    )

    if content_type not in ALLOWED_PET_PHOTO_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Documento no admitido. Usá JPEG, PNG o WebP.",
        )

    try:
        data = await document.read(MAX_PET_PHOTO_BYTES + 1)
    finally:
        await document.close()

    if not data:
        raise HTTPException(status_code=400, detail="Archivo vacío")

    if len(data) > MAX_PET_PHOTO_BYTES:
        raise HTTPException(
            status_code=413,
            detail="El documento supera el máximo de 8 MB.",
        )

    if not valid_pet_image_signature(data, content_type):
        raise HTTPException(
            status_code=415,
            detail="El contenido no coincide con el formato declarado.",
        )

    formats = {
        "image/jpeg": "JPEG",
        "image/png": "PNG",
        "image/webp": "WEBP",
    }

    try:
        with warnings.catch_warnings():
            warnings.simplefilter(
                "error",
                Image.DecompressionBombWarning,
            )

            with Image.open(BytesIO(data)) as image:
                if image.format != formats[content_type]:
                    raise ValueError("Formato real diferente")

                width, height = image.size
                if width <= 0 or height <= 0:
                    raise ValueError("Dimensiones inválidas")

                if width * height > MAX_PET_PHOTO_PIXELS:
                    raise HTTPException(
                        status_code=413,
                        detail="La imagen supera 20 millones de píxeles.",
                    )

                image.verify()

            with Image.open(BytesIO(data)) as image:
                if image.format != formats[content_type]:
                    raise ValueError("Formato real diferente")
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
            status_code=415,
            detail="Documento inválido o dañado.",
        )

    # El ID almacenado es privado; nunca se devuelve en la respuesta.
    try:
        private_id = store_pet_health_document(
            data,
            current_user.id,
            pet.id,
            content_type,
        )
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="No se pudo almacenar el documento sanitario.",
        )

    record = PetHealthDocument(
        pet_id=pet.id,
        public_id=private_id,
        content_type=content_type,
    )

    try:
        db.add(record)
        db.commit()
    except Exception:
        db.rollback()
        # Limpiar solo el archivo recién subido, nunca uno anterior.
        try:
            remove_pet_health_document(
                private_id,
                current_user.id,
                pet.id,
            )
        except Exception:
            pass

        raise HTTPException(
            status_code=500,
            detail="No se pudo registrar el documento sanitario.",
        )

    db.refresh(record)

    return {
        "id": record.id,
        "pet_id": record.pet_id,
        "content_type": record.content_type,
        "created_at": record.created_at,
    }

# ---- CL143: acceso y eliminacion de documentos sanitarios ----

@router.get(
    "/{pet_id}/health-documents/{document_id}/temporary-url"
)
def get_pet_health_document_temporary_url(
    pet_id: int,
    document_id: int,
    current_user: User = Depends(require_role(UserRole.OWNER)),
    db: Session = Depends(get_db),
):
    import re
    from time import time
    from cloudinary.utils import private_download_url

    if pet_id <= 0 or document_id <= 0:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    record = (
        db.query(PetHealthDocument)
        .join(Pet, Pet.id == PetHealthDocument.pet_id)
        .filter(
            Pet.id == pet_id,
            Pet.owner_id == current_user.id,
            PetHealthDocument.id == document_id,
        )
        .first()
    )

    if record is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    expected_folder = (
        f"woffygo/pet-health/{current_user.id}/{pet_id}"
    )

    expected_pattern = (
        re.escape(expected_folder) + r"/health_[0-9a-f]{32}"
    )

    if re.fullmatch(
        expected_pattern,
        record.public_id,
        flags=re.ASCII,
    ) is None:
        raise HTTPException(status_code=404, detail="Documento no disponible")

    extensions = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }

    extension = extensions.get(record.content_type)
    if extension is None:
        raise HTTPException(status_code=404, detail="Documento no disponible")

    try:
        expires_at = int(time()) + 60

        signed_url = private_download_url(
            record.public_id,
            extension,
            resource_type="image",
            type="authenticated",
            expires_at=expires_at,
        )
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="No se pudo preparar el acceso al documento.",
        )

    if not isinstance(signed_url, str) or not signed_url.startswith("https://"):
        raise HTTPException(
            status_code=502,
            detail="No se pudo preparar el acceso seguro.",
        )

    return {
        "url": signed_url,
        "expires_in": 60,
    }


@router.delete(
    "/{pet_id}/health-documents/{document_id}",
    status_code=204,
)
def delete_pet_health_document_endpoint(
    pet_id: int,
    document_id: int,
    current_user: User = Depends(require_role(UserRole.OWNER)),
    db: Session = Depends(get_db),
):
    if pet_id <= 0 or document_id <= 0:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    record = (
        db.query(PetHealthDocument)
        .join(Pet, Pet.id == PetHealthDocument.pet_id)
        .filter(
            Pet.id == pet_id,
            Pet.owner_id == current_user.id,
            PetHealthDocument.id == document_id,
        )
        .with_for_update(of=PetHealthDocument)
        .first()
    )

    if record is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    try:
        removed = remove_pet_health_document(
            record.public_id,
            current_user.id,
            pet_id,
        )
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=502,
            detail="No se pudo confirmar la eliminación del documento.",
        )

    if not removed:
        db.rollback()
        raise HTTPException(
            status_code=502,
            detail="La eliminación del archivo no fue confirmada.",
        )

    try:
        db.delete(record)
        db.commit()
    except Exception:
        db.rollback()
        # El archivo externo ya fue eliminado. No reintentar
        # automáticamente; requiere conciliación manual.
        raise HTTPException(
            status_code=500,
            detail=(
                "El archivo fue eliminado, pero no se pudo "
                "confirmar la actualización del registro."
            ),
        )

    return None
