"""Represent field-relative anomaly polygon geometry and statistics."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class SatelliteAnomalyProperties(BaseModel):
    id: UUID

    satellite_observation_id: UUID
    field_id: UUID

    zone_index: int

    index_type: str
    anomaly_type: str

    severity: str

    pixel_count: int

    area_sqm: float
    area_acres: float

    zone_mean_value: float
    zone_min_value: float
    zone_max_value: float | None

    field_mean_value: float
    field_median_value: float

    threshold_value: float

    difference_from_field: float
    percent_difference: float | None

    detection_method: str


class SatelliteAnomalyFeature(BaseModel):
    type: Literal["Feature"] = "Feature"

    id: UUID

    geometry: dict

    properties: SatelliteAnomalyProperties


class SatelliteAnomalyFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"

    features: list[SatelliteAnomalyFeature]
