"""Serialize chronological farm operations and related crop context."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel


class TimelineItem(BaseModel):
    type: Literal["activity"] = "activity"

    id: UUID
    occurred_at: datetime

    activity_type: str
    notes: str | None
    details: dict[str, Any]

    crop_cycle_id: UUID | None

    crop_name: str | None = None
    variety: str | None = None

    season_id: UUID | None = None
    season_name: str | None = None
