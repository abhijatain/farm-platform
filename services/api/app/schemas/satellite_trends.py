"""Describe per-date sensor metrics and farm activity timeline markers."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class SatelliteTrendPoint(BaseModel):
    observation_id: UUID
    observed_on: date

    source: str
    metric_type: str

    mean: float | None
    median: float | None
    valid_pixel_percent: float | None

    orbit_state: str | None
    relative_orbit: int | None
    platform: str | None
    radar_orbit_key: str | None

    anomaly_zone_count: int
    anomaly_area_acres: float


class SatelliteTrendActivity(BaseModel):
    id: UUID
    occurred_at: datetime
    activity_type: str
    notes: str | None
    crop_cycle_id: UUID | None


class FieldSatelliteTrendsResponse(BaseModel):
    field_id: UUID
    crop_cycle_id: UUID | None

    start_date: date
    end_date: date

    metric_types: list[str]

    points: list[SatelliteTrendPoint]
    activities: list[SatelliteTrendActivity]
