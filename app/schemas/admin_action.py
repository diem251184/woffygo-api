from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AdminActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    admin_id: int | None
    admin_email: str
    action: str
    target_type: str
    target_id: int | None
    description: str
    created_at: datetime


class AdminStats(BaseModel):
    # Usuarios
    users_total: int
    users_active: int
    users_owners: int
    users_walkers: int
    users_admins: int
    walkers_online_now: int

    # Paseos
    walks_total: int
    walks_pending: int
    walks_accepted: int
    walks_in_progress: int
    walks_completed: int
    walks_cancelled: int
    walks_today: int
    walks_this_month: int

    # Dinero
    revenue_total: str
    revenue_this_month: str
    escrow_pending_total: str
    disputed_total: str

    # Moderacion
    flagged_walks: int
    disputed_payments: int
