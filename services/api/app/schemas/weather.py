"""Weather context exposed independently from satellite observations."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


WeatherSource = Literal[
    "historical",
    "historical_forecast",
    "recent_model",
    "forecast",
]


class WeatherDay(BaseModel):
    date: date
    source: WeatherSource
    precipitation_mm: float | None = None
    temperature_max_c: float | None = None
    temperature_min_c: float | None = None
    relative_humidity_mean_percent: float | None = None
    wind_speed_max_kmh: float | None = None
    reference_et0_mm: float | None = None
    weather_code: int | None = None


class FieldWeatherResponse(BaseModel):
    field_id: UUID
    provider: str = "Open-Meteo"
    latitude: float
    longitude: float
    timezone: str
    start_date: date
    end_date: date
    forecast_end_date: date | None
    days: list[WeatherDay] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
