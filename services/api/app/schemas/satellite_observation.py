from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SatelliteObservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    field_id: UUID

    observed_on: date

    source: str
    scene_id: str

    cloud_cover_percent: float | None

    valid_pixel_percent: float | None

    ndvi_mean: float | None

    ndvi_min: float | None

    ndvi_max: float | None

    ndvi_std: float | None

    ndwi_mean: float | None

    metadata_json: dict

    ndvi_median: float | None

    ndvi_raster_uri: str | None

    resolution_m: float | None

    pixel_count: int | None

    valid_pixel_count: int | None
