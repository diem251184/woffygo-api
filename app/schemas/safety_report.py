from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from app.models.safety_report import SafetyCategory


class SafetyReportCreate(BaseModel):
    category: SafetyCategory
    description: str | None = Field(default=None, max_length=500)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    walk_id: int | None = None


class SafetyReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: SafetyCategory
    description: str | None
    latitude: float
    longitude: float
    verified: bool
    created_at: datetime
    expires_at: datetime
    reporter_id: int
    reporter_name: str
    reporter_role: str
    walk_id: int | None


class SafetyReportAdminResponse(SafetyReportResponse):
    deleted: bool
    deleted_reason: str | None


class SafetyReportDeleteRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=300)
