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
        species=payload.species,
        is_ppp=payload.is_ppp,
        has_special_needs=payload.has_special_needs,
        sex=payload.sex,
        breed=payload.breed,
        age_years=payload.age_years,
        notes=payload.notes,
        size=payload.size,
        weight_kg=payload.weight_kg,
        aggressive_with_dogs=payload.aggressive_with_dogs,
        aggressive_with_people=payload.aggressive_with_people,
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

    next_species = payload.species if "species" in payload.model_fields_set else pet.species
    next_ppp = payload.is_ppp if "is_ppp" in payload.model_fields_set else pet.is_ppp

    if next_species != pet.species:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se puede cambiar la especie de una mascota existente.",
        )

    if next_species == "cat" and next_ppp is True:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Un gato no puede declararse como PPP. Revisá la especie y la declaración.",
        )

    pet.species = next_species
    pet.is_ppp = next_ppp

    if "has_special_needs" in payload.model_fields_set:
        if payload.has_special_needs is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La declaracion de necesidades especiales debe ser true o false.",
            )
        pet.has_special_needs = payload.has_special_needs

    if "sex" in payload.model_fields_set:
        pet.sex = payload.sex

    if payload.name is not None:
        pet.name = payload.name
    if "breed" in payload.model_fields_set:
        pet.breed = payload.breed
    if "age_years" in payload.model_fields_set:
        pet.age_years = payload.age_years
    if "notes" in payload.model_fields_set:
        pet.notes = payload.notes
    if "size" in payload.model_fields_set:
        if pet.species == "dog" and payload.size is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El tamaño corporal es obligatorio para perros.",
            )
        pet.size = payload.size
    if "weight_kg" in payload.model_fields_set:
        pet.weight_kg = payload.weight_kg
    if payload.aggressive_with_dogs is not None:
        pet.aggressive_with_dogs = payload.aggressive_with_dogs
    if payload.aggressive_with_people is not None:
        pet.aggressive_with_people = payload.aggressive_with_people

    db.commit()
    db.refresh(pet)
    return pet


def delete_pet(db: Session, pet_id: int, user: User) -> None:
    pet = _get_pet_or_404(db, pet_id)
    _ensure_owner(pet, user)

    # No permitir borrar si tiene paseos asociados (RESTRICT en FK)
    if pet.booking_associations:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede eliminar una mascota con paseos asociados",
        )

    db.delete(pet)
    db.commit()