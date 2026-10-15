from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


SatelliteChangeMode = Literal[
    "previous",
    "crop_start",
    "days_7",
    "days_14",
    "days_30",
    "custom",
]

SatelliteChangeStatus = Literal[
    "complete",
    "missing_current",
    "missing_baseline",
]


class SatelliteChangeObservation(BaseModel):
    observation_id: UUID

    observed_on: date

    source: str
    scene_id: str

    orbit_state: str | None
    relative_orbit: int | None
    platform: str | None

    metric_type: str

    valid_pixel_percent: float | None

    mean: float | None
    median: float | None

    minimum: float | None
    maximum: float | None
    std: float | None

    raster_uri: str

    native_resolution_m: float | None
    output_resolution_m: float | None


class SatelliteChangeScalarSummary(BaseModel):
    days_between: int | None

    mean_change: float | None
    mean_percent_change: float | None

    median_change: float | None
    median_percent_change: float | None


class SatelliteChangeAnomalySummary(BaseModel):
    persistence_basis: str

    before_anomaly_area_sqm: float | None
    before_anomaly_area_acres: float | None

    after_anomaly_area_sqm: float | None
    after_anomaly_area_acres: float | None

    persistent_area_sqm: float | None
    persistent_area_acres: float | None

    resolved_area_sqm: float | None
    resolved_area_acres: float | None

    new_area_sqm: float | None
    new_area_acres: float | None

    persistent_geometry: dict | None
    resolved_geometry: dict | None
    new_geometry: dict | None


class FieldSatelliteChangeResponse(BaseModel):
    field_id: UUID

    metric_type: str
    mode: SatelliteChangeMode
    status: SatelliteChangeStatus

    requested_to_date: date | None
    requested_from_date: date | None

    baseline_target_date: date | None

    crop_cycle_id: UUID | None
    crop_reference_date: date | None

    minimum_valid_percent: float
    date_tolerance_days: int

    pixel_change_threshold: float
    pixel_change_display_max: float

    before: SatelliteChangeObservation | None
    after: SatelliteChangeObservation | None

    scalar: SatelliteChangeScalarSummary

    anomalies: SatelliteChangeAnomalySummary
