"""Validate activity creation and serialize field operations."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class ActivityCreate(BaseModel):
    crop_cycle_id: UUID | None = None

    activity_type: str = Field(
        min_length=1,
        max_length=40,
    )

    occurred_at: datetime

    notes: str | None = None

    details: dict[str, Any] = Field(
        default_factory=dict
    )

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(
        cls,
        value: datetime,
    ) -> datetime:

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "occurred_at must include a timezone."
            )

        return value


class ActivityResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID

    field_id: UUID
    crop_cycle_id: UUID | None

    activity_type: str
    occurred_at: datetime

    notes: str | None
    details: dict[str, Any]

    created_at: datetime
    updated_at: datetime
