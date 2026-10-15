"""Field-centric modeled weather context via Open-Meteo.

Historical reanalysis, recent modeled conditions and forecasts retain
different source labels. No weather reading is represented as on-field sensor
data. Failed provider requests are never converted into zero rainfall.
"""
from __future__ import annotations

import json
import math
import threading
import time
from datetime import date, datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import UUID

from app.core.config import settings
from app.schemas.weather import FieldWeatherResponse, WeatherDay


DAILY_VARIABLES = (
    "precipitation_sum",
    "temperature_2m_max",
    "temperature_2m_min",
    "relative_humidity_2m_mean",
    "wind_speed_10m_max",
    "et0_fao_evapotranspiration",
    "weather_code",
)
FIELD_MAP = {
    "precipitation_mm": "precipitation_sum",
    "temperature_max_c": "temperature_2m_max",
    "temperature_min_c": "temperature_2m_min",
    "relative_humidity_mean_percent": "relative_humidity_2m_mean",
    "wind_speed_max_kmh": "wind_speed_10m_max",
    "reference_et0_mm": "et0_fao_evapotranspiration",
}
# Memory cache is per API worker (a future Redis cache could replace it).
_CACHE: dict[tuple, tuple[float, dict]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_MAX_ENTRIES = 512


class WeatherProviderError(Exception):
    pass


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _endpoint(*, archive: bool) -> str:
    commercial = bool(settings.weather_api_key)
    if archive:
        host = (
            "customer-archive-api.open-meteo.com"
            if commercial else "archive-api.open-meteo.com"
        )
        return "https://" + host + "/v1/archive"
    host = (
        "customer-api.open-meteo.com"
        if commercial else "api.open-meteo.com"
    )
    return "https://" + host + "/v1/forecast"


def _fetch_weather(*, archive: bool, params: dict) -> dict:
    """Fixed provider hosts; key never exposed to browsers or logs."""
    if settings.environment.lower() in ("production", "prod") and not settings.weather_api_key:
        raise WeatherProviderError(
            "Configure WEATHER_API_KEY for commercial production use."
        )
    params = {**params, "daily": ",".join(DAILY_VARIABLES), "timezone": "auto"}
    if settings.weather_api_key:
        params["apikey"] = settings.weather_api_key.get_secret_value()
    key = (archive, tuple(sorted(
        (k, str(v)) for k, v in params.items() if k != "apikey"
    )), bool(settings.weather_api_key))
    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and cached[0] > now:
            return cached[1]

    url = _endpoint(archive=archive) + "?" + urlencode(params)
    try:
        with urlopen(
            Request(url, headers={"User-Agent": "FarmPlatform/1.0"}),
            timeout=10,
        ) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise WeatherProviderError("Weather response exceeded size limit.")
        payload = json.loads(raw)
        if (
            not isinstance(payload, dict)
            or payload.get("error")
            or not isinstance(payload.get("daily"), dict)
            or not isinstance(payload["daily"].get("time"), list)
        ):
            raise WeatherProviderError("Weather provider returned invalid data.")
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        raise WeatherProviderError("Weather service is temporarily unavailable.") from exc

    with _CACHE_LOCK:
        if len(_CACHE) >= _CACHE_MAX_ENTRIES:
            _CACHE.clear()
        _CACHE[key] = (now + (21_600 if archive else 900), payload)
    return payload


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _parse_daily(payload: dict, source: str, *, today: date) -> list[WeatherDay]:
    """Align arrays by date; nulls stay null instead of becoming 0 mm."""
    daily = payload.get("daily", {})
    dates = daily.get("time", [])
    if not isinstance(dates, list):
        raise WeatherProviderError("Weather provider returned malformed dates.")
    results = []
    for index, date_str in enumerate(dates):
        try:
            day = date.fromisoformat(date_str)
        except (ValueError, TypeError) as exc:
            raise WeatherProviderError("Weather provider returned an invalid date.") from exc
        day_source = source
        if source == "recent_model" and day > today:
            day_source = "forecast"
        values = {}
        for target, upstream in FIELD_MAP.items():
            readings = daily.get(upstream)
            values[target] = (
                _number(readings[index])
                if isinstance(readings, list) and index < len(readings)
                else None
            )
        codes = daily.get("weather_code")
        raw_code = (
            _number(codes[index])
            if isinstance(codes, list) and index < len(codes)
            else None
        )
        results.append(WeatherDay(
            date=day,
            source=day_source,
            weather_code=int(raw_code) if raw_code is not None else None,
            **values,
        ))
    return results


def load_field_weather(
    *,
    field_id: UUID,
    latitude: float,
    longitude: float,
    start_date: date,
    end_date: date,
    include_forecast: bool = True,
) -> FieldWeatherResponse:
    today = _today()
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("Field centroid is outside valid coordinates.")
    if end_date > today:
        raise ValueError("end_date cannot be in the future.")
    if start_date > end_date or (end_date - start_date).days > 366:
        raise ValueError("Choose a historical weather window of at most 367 days.")
    if start_date < date(1940, 1, 1):
        raise ValueError("Weather history starts in 1940.")

    # Open-Meteo reanalysis can lag; last 7 days come from forecast
    # model runs rather than pretending late reanalysis is available.
    archive_end = min(end_date, today - timedelta(days=8))
    newest_start = today - timedelta(days=7)
    forecast_end = today + timedelta(days=6) if include_forecast else None

    records: dict[date, WeatherDay] = {}
    warnings: list[str] = []
    timezone_name = "auto"

    base = {"latitude": round(latitude, 5), "longitude": round(longitude, 5)}
    if start_date <= archive_end:
        try:
            historical = _fetch_weather(
                archive=True,
                params={
                    **base,
                    "start_date": start_date.isoformat(),
                    "end_date": archive_end.isoformat(),
                },
            )
            timezone_name = str(historical.get("timezone") or timezone_name)
            for entry in _parse_daily(historical, "historical", today=today):
                if start_date <= entry.date <= end_date:
                    records[entry.date] = entry
        except WeatherProviderError:
            warnings.append("Historical weather is temporarily unavailable.")

    if end_date >= newest_start or include_forecast:
        try:
            recent = _fetch_weather(
                archive=False,
                params={**base, "past_days": 7, "forecast_days": 7},
            )
            timezone_name = str(recent.get("timezone") or timezone_name)
            for entry in _parse_daily(recent, "recent_model", today=today):
                if (
                    (start_date <= entry.date <= end_date)
                    or (include_forecast and today < entry.date <= forecast_end)
                ):
                    # Real historical reanalysis wins if ranges overlap.
                    records.setdefault(entry.date, entry)
        except WeatherProviderError:
            warnings.append("Recent weather and forecast are temporarily unavailable.")

    if not records:
        raise WeatherProviderError(
            "No weather data is available for the selected field and dates."
        )

    return FieldWeatherResponse(
        field_id=field_id,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone_name,
        start_date=start_date,
        end_date=end_date,
        forecast_end_date=forecast_end,
        days=sorted(records.values(), key=lambda entry: entry.date),
        warnings=warnings,
    )
