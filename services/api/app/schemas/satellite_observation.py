"""Describe ingested satellite observations and job status."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_serializer

from app.schemas.private_storage import public_metadata


class SatelliteMetricResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    satellite_observation_id: UUID

    metric_type: str
    # Input-only ORM data. Never serialize a private object URI to clients.
    raster_uri: str = Field(exclude=True)

    @computed_field
    @property
    def has_raster(self) -> bool:
        return bool(self.raster_uri)

    mean: float | None
    median: float | None
    min: float | None
    max: float | None
    std: float | None

    native_resolution_m: float | None
    output_resolution_m: float | None

    pixel_count: int | None
    valid_pixel_count: int | None
    valid_pixel_percent: float | None

    metadata_json: dict

    @field_serializer("metadata_json")
    def redact_storage_metadata(self, value: dict) -> dict:
        return public_metadata(value)


class SatelliteObservationResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    field_id: UUID

    observed_on: date

    source: str
    scene_id: str

    cloud_cover_percent: float | None

    metadata_json: dict

    @field_serializer("metadata_json")
    def redact_storage_metadata(self, value: dict) -> dict:
        return public_metadata(value)

    metrics: list[SatelliteMetricResponse] = Field(
        default_factory=list,
    )

    created_at: datetime
    updated_at: datetime


class SatelliteIngestionJobResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    field_id: UUID

    job_type: str

    start_date: date
    end_date: date

    status: str

    attempts: int
    max_attempts: int

    available_at: datetime

    started_at: datetime | None
    completed_at: datetime | None

    last_error: str | None

    @field_serializer("last_error")
    def redact_internal_job_error(self, value: str | None) -> str | None:
        # Worker exception strings can contain private GCS paths.
        return public_metadata(value)

    created_at: datetime
    updated_at: datetime
