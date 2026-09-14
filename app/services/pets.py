"""Servicio CRUD de mascotas."""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.pet import Pet
from app.models.user import User
from app.schemas.pet import PetCreate, PetUpdate


def _get_pet_or_404(db: Session, pet_id: int) -> Pet:
    pet = db.get(Pet, pet_id)
    if pet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mascota no encontrada",
        )
    return pet


def _ensure_owner(pet: Pet, user: User) -> None:
    if pet.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta mascota no te pertenece",
        )


def create_pet(db: Session, owner: User, payload: PetCreate) -> Pet:
    pet = Pet(
        owner_id=owner.id,
        name=payload.name,
        breed=payload.breed,
        age_years=payload.age_years,
        notes=payload.notes,
    )
    db.add(pet)
    db.commit()
    db.refresh(pet)
    return pet


def list_my_pets(db: Session, owner: User) -> list[Pet]:
    return (
        db.query(Pet)
        .filter(Pet.owner_id == owner.id)
        .order_by(Pet.created_at.asc())
        .all()
    )


def get_pet(db: Session, pet_id: int, user: User) -> Pet:
    pet = _get_pet_or_404(db, pet_id)
    _ensure_owner(pet, user)
    return pet


def update_pet(db: Session, pet_id: int, user: User, payload: PetUpdate) -> Pet:
    pet = _get_pet_or_404(db, pet_id)
    _ensure_owner(pet, user)

    if payload.name is not None:
        pet.name = payload.name
    if payload.breed is not None:
        pet.breed = payload.breed
    if payload.age_years is not None:
        pet.age_years = payload.age_years
    if payload.notes is not None:
        pet.notes = payload.notes

    db.commit()
    db.refresh(pet)
    return pet


def delete_pet(db: Session, pet_id: int, user: User) -> None:
    pet = _get_pet_or_404(db, pet_id)
    _ensure_owner(pet, user)

    # No permitir borrar si tiene paseos asociados (RESTRICT en FK)
    if pet.walk_pets:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede eliminar una mascota con paseos asociados",
        )

    db.delete(pet)
    db.commit()