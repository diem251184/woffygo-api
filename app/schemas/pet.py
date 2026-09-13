from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PetMinimal(BaseModel):
    """Version liviana de una mascota para embeber en respuestas de Walk."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    breed: str | None


class PetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    breed: str | None = Field(default=None, max_length=80)
    age_years: int | None = Field(default=None, ge=0, le=30)
    notes: str | None = Field(default=None, max_length=500)


class PetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    breed: str | None = Field(default=None, max_length=80)
    age_years: int | None = Field(default=None, ge=0, le=30)
    notes: str | None = Field(default=None, max_length=500)


class PetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    name: str
    breed: str | None
    age_years: int | None
    notes: str | None
    created_at: datetime