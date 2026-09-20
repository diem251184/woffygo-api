from pydantic import BaseModel, Field


class DeviceTokenCreate(BaseModel):
    token: str = Field(min_length=10, max_length=255)
    platform: str = Field(default="android", max_length=20)
