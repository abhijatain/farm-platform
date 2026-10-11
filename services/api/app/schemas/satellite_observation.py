from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SatelliteMetricResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID

    satellite_observation_id: UUID

    metric_type: str

    raster_uri: str

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
    valid_pixel_percent: float | None

    # -------------------------------------------------
    # Legacy NDVI fields
    #
    # Keep these temporarily because older frontend/API
    # code may still depend on them.
    # -------------------------------------------------

    ndvi_mean: float | None
    ndvi_median: float | None

    ndvi_min: float | None
    ndvi_max: float | None

    ndvi_std: float | None

    ndwi_mean: float | None

    ndvi_raster_uri: str | None

    resolution_m: float | None

    pixel_count: int | None
    valid_pixel_count: int | None

    metadata_json: dict

    # -------------------------------------------------
    # Generic satellite metrics
    #
    # NDVI, NDRE, NDMI, GNDVI, EVI2,
    # NDWI, SAVI, MSAVI, BSI, NDTI,
    # CCCI, RECI, MCARI
    # -------------------------------------------------

    metrics: list[SatelliteMetricResponse] = Field(
        default_factory=list,
    )
