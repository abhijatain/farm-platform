"""Explainable field-level radar screening, never a crop-health diagnosis."""
from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class RadarScreenMetric(BaseModel):
    metric_type: Literal["sar_vh_db", "sar_vv_db", "sar_rvi"]
    unit: str
    status: Literal[
        "unusual_variation", "within_reference_range",
        "insufficient_baseline", "unverified_stage",
    ]
    latest_value: float
    reference_median: float | None = None
    difference: float | None = None
    screening_threshold: float | None = None
    baseline_passes: int
    required_baseline_passes: int = 3


class RadarWeatherContext(BaseModel):
    precipitation_3_day_mm: float | None = None
    days_available: int
    days_required: int = 3
    wet_weather_context: bool | None = None


class RadarOpticalContext(BaseModel):
    metric_type: Literal["ndvi", "ndmi"]
    observed_on: date
    value: float
    days_from_radar: int


class RadarOrbitScreen(BaseModel):
    radar_orbit_key: str
    orbit_state: str
    relative_orbit: int
    platform: str | None
    observed_on: date
    stage_code: str | None
    stage_label: str | None
    stage_source: Literal["farmer_confirmed", "provisional", "unknown"]
    status: Literal["review_variation", "within_reference_range", "insufficient_evidence"]
    metrics: list[RadarScreenMetric]
    weather: RadarWeatherContext
    optical: list[RadarOpticalContext]
    nearby_activities: list[str]
    explanations: list[str]


class CropRadarScreeningResponse(BaseModel):
    crop_cycle_id: UUID
    field_id: UUID
    crop_name: str
    profile_key: str
    as_of: date
    analysis_version: str = "field-radar-screening-v1"
    minimum_valid_coverage_percent: float = 80.0
    minimum_prior_same_stage_passes: int = 3
    orbits: list[RadarOrbitScreen] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    statement: str = (
        "Exploratory field-median radar screening only. Not a disease, "
        "water-stress, nutrient-deficiency or crop-health diagnosis; no "
        "pixel-level SAR anomaly polygons or automatic alerts are produced."
    )
