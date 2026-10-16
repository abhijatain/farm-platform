"""Crop stages are either farmer-recorded or provisional day-based estimates."""
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StageDefinition(BaseModel):
    code: str
    label: str
    approx_days_after_planting: int | None
    bbch_reference: str | None = None


class StageObservationInput(BaseModel):
    stage_code: str = Field(min_length=1, max_length=40)
    observed_on: date
    notes: str | None = Field(default=None, max_length=2000)


class StageObservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    crop_cycle_id: UUID
    stage_code: str
    observed_on: date
    notes: str | None
    created_at: datetime
    updated_at: datetime


class CropGrowthResponse(BaseModel):
    crop_cycle_id: UUID
    crop_name: str
    profile_key: str
    profile_version: str
    planting_date: date | None
    as_of: date
    days_after_planting: int | None
    stages: list[StageDefinition]
    observations: list[StageObservationResponse]
    latest_recorded_stage: str | None
    provisional_stage: str | None
    degree_day_base_c: float | None
    accumulated_gdd_c_days: float | None
    gdd_days_available: int
    gdd_days_expected: int
    warnings: list[str] = Field(default_factory=list)
