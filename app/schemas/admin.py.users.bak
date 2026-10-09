from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class WalkVerificationDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    walk_id: int
    owner_id: int
    walker_id: int | None
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    duration_minutes_expected: int
    duration_real_minutes: float | None
    distance_meters: Decimal | None
    avg_speed_kmh: float | None
    flagged: bool
    reason: str | None


class FlagClearRequest(BaseModel):
    note: str | None = None