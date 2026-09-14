from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.models.user import User, UserRole
from app.schemas.pet import PetCreate, PetResponse, PetUpdate
from app.services import pets as pets_service


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