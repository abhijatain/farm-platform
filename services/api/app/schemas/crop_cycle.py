from datetime import date, datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class CropCycleCreate(BaseModel):
    field_id: UUID

    crop_name: str = Field(
        min_length=1,
        max_length=100,
    )

    variety: str | None = Field(
        default=None,
        max_length=100,
    )

    started_on: date

    planted_on: date | None = None
    expected_harvest_on: date | None = None
    harvested_on: date | None = None

    notes: str | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if (
            self.planted_on is not None
            and self.planted_on < self.started_on
        ):
            raise ValueError(
                "planted_on cannot be before started_on."
            )

        reference_date = (
            self.planted_on
            or self.started_on
        )

        if (
            self.expected_harvest_on is not None
            and self.expected_harvest_on
            < reference_date
        ):
            raise ValueError(
                "expected_harvest_on cannot be "
                "before planting/start date."
            )

        if (
            self.harvested_on is not None
            and self.harvested_on
            < reference_date
        ):
            raise ValueError(
                "harvested_on cannot be "
                "before planting/start date."
            )

        return self


class CropCycleResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID

    season_id: UUID
    field_id: UUID

    crop_name: str
    variety: str | None

    status: str

    started_on: date
    planted_on: date | None
    expected_harvest_on: date | None
    harvested_on: date | None

    notes: str | None

    created_at: datetime
    updated_at: datetime
