from datetime import datetime
from pydantic import BaseModel
from typing import Optional

class TariffBase(BaseModel):
    service_type: str
    base_price: float
    per_km_price: Optional[float] = None
    extra_pet_price: float
    ipc_applied: float
    is_active: bool

class TariffResponse(TariffBase):
    id: int
    valid_from: datetime
    valid_to: Optional[datetime] = None
    approved_by: Optional[int] = None

    class Config:
        from_attributes = True