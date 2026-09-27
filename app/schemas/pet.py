from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


PetSize = Literal["chico", "mediano", "grande"]


class PetMinimal(BaseModel):
    """Version liviana de una mascota para embeber en respuestas de Walk."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    breed: str | None
    size: str | None
    aggressive_with_dogs: bool
    aggressive_with_people: bool


class PetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    breed: str | None = Field(default=None, max_length=80)
    age_years: int | None = Field(default=None, ge=0, le=30)
    notes: str | None = Field(default=None, max_length=500)
    size: PetSize = Field(
        description="Tamaño del perro: chico, mediano o grande"
    )
    weight_kg: float | None = Field(default=None, ge=0, le=120)
    aggressive_with_dogs: bool = False
    aggressive_with_people: bool = False


class PetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    breed: str | None = Field(default=None, max_length=80)
    age_years: int | None = Field(default=None, ge=0, le=30)
    notes: str | None = Field(default=None, max_length=500)
    size: PetSize | None = None
    weight_kg: float | None = Field(default=None, ge=0, le=120)
    aggressive_with_dogs: bool | None = None
    aggressive_with_people: bool | None = None


class PetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    name: str
    breed: str | None
    age_years: int | None
    notes: str | None
    size: str | None
    weight_kg: float | None
    aggressive_with_dogs: bool
    aggressive_with_people: bool
    created_at: datetime