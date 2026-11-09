from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


PetSize = Literal["chico", "mediano", "grande"]
PetSpecies = Literal["dog", "cat"]
PetSex = Literal["male", "female"]


class PetMinimal(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    species: PetSpecies = "dog"
    has_special_needs: bool = False
    is_ppp: bool | None = None
    sex: PetSex | None = None

    id: int
    name: str
    breed: str | None
    size: str | None
    photo_url: str | None = None
    aggressive_with_dogs: bool
    aggressive_with_people: bool


class PetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    species: PetSpecies = "dog"
    has_special_needs: bool = False
    is_ppp: bool | None = None
    sex: PetSex | None = None
    breed: str | None = Field(default=None, max_length=80)
    age_years: int | None = Field(default=None, ge=0, le=30)
    notes: str | None = Field(default=None, max_length=500)
    size: PetSize | None = Field(
        default=None,
        description="Obligatorio para perros; opcional para gatos."
    )
    weight_kg: float | None = Field(default=None, ge=0, le=120)
    photo_url: str | None = None
    aggressive_with_dogs: bool = False
    aggressive_with_people: bool = False

    @model_validator(mode="after")
    def validate_ppp_species(self):
        if self.species == "cat" and self.is_ppp is True:
            raise ValueError("Un gato no puede declararse como PPP.")
        if self.species == "dog" and self.size is None:
            raise ValueError("El tamaño corporal es obligatorio para perros.")
        return self


class PetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    species: PetSpecies | None = None
    has_special_needs: bool | None = None
    is_ppp: bool | None = None
    sex: PetSex | None = None
    breed: str | None = Field(default=None, max_length=80)
    age_years: int | None = Field(default=None, ge=0, le=30)
    notes: str | None = Field(default=None, max_length=500)
    size: PetSize | None = None
    weight_kg: float | None = Field(default=None, ge=0, le=120)
    photo_url: str | None = None
    aggressive_with_dogs: bool | None = None
    aggressive_with_people: bool | None = None


class PetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    species: PetSpecies = "dog"
    has_special_needs: bool = False
    is_ppp: bool | None = None
    sex: PetSex | None = None

    id: int
    owner_id: int
    name: str
    breed: str | None
    age_years: int | None
    notes: str | None
    photo_url: str | None = None
    size: str | None
    weight_kg: float | None
    aggressive_with_dogs: bool
    aggressive_with_people: bool
    created_at: datetime
