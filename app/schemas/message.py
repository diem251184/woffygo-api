from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    walk_id: int
    sender_id: int
    filtered_text: str
    was_blocked: bool
    block_reason: str | None
    created_at: datetime


class MessageAdminResponse(MessageResponse):
    """Solo para admins: incluye el texto original sin filtrar."""

    text: str