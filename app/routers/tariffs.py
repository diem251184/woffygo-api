from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone

from app.core.database import get_db
from app.models.tariff import TariffHistory
from app.schemas.tariff import TariffResponse

router = APIRouter(prefix="/api/v1/tariffs", tags=["Tariffs"])

@router.get("/current", response_model=List[TariffResponse])
def get_current_tariffs(db: Session = Depends(get_db)):
    tariffs = db.query(TariffHistory).filter(TariffHistory.is_active == True).all()

    if not tariffs:
        return [
            {
                "id": 0,
                "service_type": "paseo",
                "base_price": 5500.0,
                "per_km_price": None,
                "extra_pet_price": 1500.0,
                "ipc_applied": 0.0,
                "is_active": True,
                "valid_from": datetime.now(timezone.utc),
                "valid_to": None,
                "approved_by": None
            },
            {
                "id": 0,
                "service_type": "taxi",
                "base_price": 4000.0,
                "per_km_price": 1000.0,
                "extra_pet_price": 0.0,
                "ipc_applied": 0.0,
                "is_active": True,
                "valid_from": datetime.now(timezone.utc),
                "valid_to": None,
                "approved_by": None
            }
        ]
    return tariffs