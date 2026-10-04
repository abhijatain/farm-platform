from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class PolygonGeometry(BaseModel):
    type: Literal["Polygon"]
    coordinates: list[list[list[float]]]

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(
        cls,
        coordinates: list[list[list[float]]],
    ) -> list[list[list[float]]]:

        if not coordinates:
            raise ValueError(
                "Polygon must contain at least one ring."
            )

        for ring in coordinates:
            if len(ring) < 4:
                raise ValueError(
                    "Each polygon ring must contain at least 4 positions."
                )

            if ring[0] != ring[-1]:
                raise ValueError(
                    "Polygon rings must be closed. "
                    "The first and last coordinates must match."
                )

            for position in ring:
                if len(position) != 2:
                    raise ValueError(
                        "Each coordinate must contain longitude and latitude."
                    )

                longitude, latitude = position

                if not -180 <= longitude <= 180:
                    raise ValueError(
                        "Longitude must be between -180 and 180."
                    )

                if not -90 <= latitude <= 90:
                    raise ValueError(
                        "Latitude must be between -90 and 90."
                    )

        return coordinates


class FieldCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=120,
    )

    boundary: PolygonGeometry


class FieldResponse(BaseModel):
    id: UUID
    farm_id: UUID

    name: str
    boundary: PolygonGeometry

    area_square_metres: float
    area_hectares: float
    area_acres: float

    created_at: datetime
    updated_at: datetime
