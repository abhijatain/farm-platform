from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FarmCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=120,
    )

    location_name: str | None = Field(
        default=None,
        max_length=255,
    )


class FarmResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    name: str
    location_name: str | None

    created_at: datetime
    updated_at: datetime
