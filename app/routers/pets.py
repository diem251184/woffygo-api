from fastapi import APIRouter, Depends, status, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.models.user import User, UserRole
from app.models.pet import Pet
from app.schemas.pet import PetCreate, PetResponse, PetUpdate
from app.services import pets as pets_service
from app.services.cloudinary_service import upload_pet_image_to_cloudinary


router = APIRouter(prefix="/pets", tags=["pets"])


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

    file_bytes = await photo.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo enviado está vacío",
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
