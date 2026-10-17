"""Represent source-aware selection of optical, radar and thermal passes."""

from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, computed_field


SatelliteSourceKind = Literal[
    "optical",
    "radar",
    "thermal",
    "other",
]

SatelliteTimelineStatus = Literal[
    "usable",
    "cloud_skipped",
    "unusable",
    "skipped",
    "unavailable",
]

SatelliteRecommendationKind = Literal[
    "preferred_metric",
    "radar_fallback",
    "none",
]


class SatelliteTimelineMetricSummary(BaseModel):
    metric_type: str

    mean: float | None
    median: float | None

    valid_pixel_percent: float | None

    raster_uri: str = Field(exclude=True)

    @computed_field
    @property
    def has_raster(self) -> bool:
        return bool(self.raster_uri)


class SatelliteTimelineEvent(BaseModel):
    observation_id: UUID

    observed_on: date

    source: str
    source_kind: SatelliteSourceKind

    scene_id: str

    status: SatelliteTimelineStatus
    processing_status: str | None

    cloud_cover_percent: float | None
    field_cloud_cover_percent: float | None

    cloud_independent: bool

    metric_types: list[str] = Field(
        default_factory=list,
    )

    representative_metric: (
        SatelliteTimelineMetricSummary
        | None
    )


class SatelliteTimelineSelectionMatch(BaseModel):
    observation_id: UUID

    observed_on: date
    days_from_target: int

    source: str
    source_kind: SatelliteSourceKind

    metric_type: str

    median: float | None
    mean: float | None

    valid_pixel_percent: float | None

    raster_uri: str


class SatelliteTimelineSelection(BaseModel):
    target_date: date

    preferred_metric_type: str
    minimum_valid_percent: float
    search_window_days: int

    optical_unavailable_on_target: bool

    preferred_metric: (
        SatelliteTimelineSelectionMatch
        | None
    )

    radar_fallback: (
        SatelliteTimelineSelectionMatch
        | None
    )

    recommended_kind: (
        SatelliteRecommendationKind
    )

    recommended: (
        SatelliteTimelineSelectionMatch
        | None
    )

    recommendation_reason: str | None


class FieldSatelliteTimelineResponse(BaseModel):
    field_id: UUID

    events: list[
        SatelliteTimelineEvent
    ]

    selection: SatelliteTimelineSelection
