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

# ============================================
# Admin - Usuarios
# ============================================

class AdminUserListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    phone: str
    role: str
    is_active: bool
    created_at: datetime


class AdminWalkerProfileInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bio: str | None
    hourly_rate: Decimal
    search_radius_km: int
    is_online: bool
    rating_avg: Decimal | None
    total_walks: int
    current_latitude: float | None = None
    current_longitude: float | None = None


class AdminUserDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    phone: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # Contadores
    pets_count: int = 0
    walks_as_owner_count: int = 0
    walks_as_walker_count: int = 0
    # Perfil walker (si aplica)
    walker_profile: AdminWalkerProfileInfo | None = None


class ToggleActiveRequest(BaseModel):
    is_active: bool
