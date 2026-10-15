"""Describe before/after activity observation and spatial change evidence."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

ComparisonStatus = Literal[
    "complete",
    "missing_before",
    "missing_after",
    "missing_both",
]


class ActivitySatelliteObservationMatch(BaseModel):
    observation_id: UUID

    observed_on: date
    days_from_activity: int

    source: str
    scene_id: str

    metric_type: str

    valid_pixel_percent: float

    mean: float | None
    median: float | None
    minimum: float | None
    maximum: float | None
    std: float | None

    raster_uri: str

    native_resolution_m: float | None
    output_resolution_m: float | None

    anomaly_zone_count: int
    anomaly_area_sqm: float
    anomaly_area_acres: float


class ActivitySatelliteComparison(BaseModel):
    status: ComparisonStatus

    mean_change: float | None
    mean_percent_change: float | None

    median_change: float | None
    median_percent_change: float | None

    anomaly_zone_count_change: int | None

    anomaly_area_sqm_change: float | None
    anomaly_area_acres_change: float | None

    percent_change_minimum_baseline_abs: float


class ActivitySatelliteSpatialComparison(BaseModel):
    status: ComparisonStatus

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


class ActivitySatelliteContextResponse(BaseModel):
    activity_id: UUID
    field_id: UUID

    activity_type: str
    occurred_at: datetime

    metric_type: str

    search_window_days: int
    minimum_valid_percent: float

    before: ActivitySatelliteObservationMatch | None
    after: ActivitySatelliteObservationMatch | None

    comparison: ActivitySatelliteComparison
    spatial_comparison: ActivitySatelliteSpatialComparison
