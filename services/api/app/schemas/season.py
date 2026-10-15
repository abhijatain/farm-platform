"""Validate growing season inputs and expose season records."""

from datetime import date, datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class SeasonCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=100,
    )

    season_type: str | None = Field(
        default=None,
        max_length=30,
    )

    started_on: date
    ended_on: date | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if (
            self.ended_on is not None
            and self.ended_on < self.started_on
        ):
            raise ValueError(
                "ended_on cannot be before started_on."
            )

        return self


class SeasonResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    farm_id: UUID

    name: str
    season_type: str | None
    status: str

    started_on: date
    ended_on: date | None

    created_at: datetime
    updated_at: datetime
