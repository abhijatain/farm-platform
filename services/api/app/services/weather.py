"""Field-centered, server-side Open-Meteo weather with explicit provenance.

Historical reanalysis, archived forecasts, current modeled weather and future
forecasts are never treated as field-station measurements. Missing days and
failed providers never become zero rainfall or temperature.
"""
from __future__ import annotations

import json
import logging
import math
import threading
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import UUID

from app.core.config import settings
from app.schemas.weather import FieldWeatherResponse, WeatherDay

logger = logging.getLogger(__name__)

# All these aggregates are valid on both the historical archive API and the
# forecast API. Daily humidity means are NOT universally exposed by forecast;
# request its hourly series on forecast endpoints and aggregate by local date.
DAILY_VARIABLES = (
    "precipitation_sum",
    "temperature_2m_max",
    "temperature_2m_min",
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
_CACHE: dict[tuple, tuple[float, dict]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_MAX_ENTRIES = 512


class WeatherProviderError(Exception):
    pass


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _has_api_key() -> bool:
    return bool(
        settings.weather_api_key
        and settings.weather_api_key.get_secret_value()
    )


def _endpoint(provider: str) -> str:
    commercial = _has_api_key()
    hosts = {
        "archive": "archive-api.open-meteo.com",
        "forecast": "api.open-meteo.com",
        "historical_forecast": "historical-forecast-api.open-meteo.com",
    }
    if provider not in hosts:
        raise ValueError("Unknown weather provider")
    host = hosts[provider]
    if commercial:
        host = "customer-" + host
    path = "/v1/archive" if provider == "archive" else "/v1/forecast"
    return "https://" + host + path


def _safe_provider_reason(raw: object) -> str | None:
    if not isinstance(raw, dict):
        return None
    reason = raw.get("reason")
    if not isinstance(reason, str):
        return None
    reason = reason.replace("\n", " ").replace("\r", " ")[:160]
    if _has_api_key():
        reason = reason.replace(settings.weather_api_key.get_secret_value(), "[redacted]")
    return reason


def _request_provider(*, provider: str, params: dict) -> dict:
    """Log only provider and sanitized errors; never include query/API keys."""
    if settings.environment.lower() in ("production", "prod") and not _has_api_key():
        raise WeatherProviderError("Configure WEATHER_API_KEY for commercial production use.")

    daily = DAILY_VARIABLES + (
        ("relative_humidity_2m_mean",) if provider == "archive" else ()
    )
    params = {
        **params,
        "daily": ",".join(daily),
        "timezone": "auto",
    }
    if provider != "archive":
        params["hourly"] = "relative_humidity_2m"
    if _has_api_key():
        params["apikey"] = settings.weather_api_key.get_secret_value()

    # Cache by provider + sanitized query, not by credential.
    key = (
        provider,
        tuple(sorted((k, str(v)) for k, v in params.items() if k != "apikey")),
        _has_api_key(),
    )
    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and cached[0] > now:
            return cached[1]

    request = Request(
        _endpoint(provider) + "?" + urlencode(params),
        headers={"User-Agent": "FarmPlatform/1.0"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise WeatherProviderError("Weather response exceeded the size limit.")
        payload = json.loads(raw)
    except HTTPError as exc:
        reason = None
        try:
            reason = _safe_provider_reason(json.loads(exc.read(8192)))
        except (ValueError, OSError):
            pass
        details = "HTTP " + str(exc.code)
        if reason:
            details += " — " + reason
        logger.warning("Open-Meteo %s request rejected: %s", provider, details)
        raise WeatherProviderError(f"Open-Meteo {provider}: {details}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        logger.warning(
            "Open-Meteo %s request failed: %s: %s",
            provider, type(exc).__name__, str(exc)[:180],
        )
        raise WeatherProviderError(
            f"Open-Meteo {provider}: network/TLS/timeout error ({type(exc).__name__})"
        ) from exc
    except (ValueError, UnicodeError) as exc:
        logger.warning("Open-Meteo %s returned invalid JSON: %s", provider, type(exc).__name__)
        raise WeatherProviderError(f"Open-Meteo {provider}: invalid JSON") from exc

    if (
        not isinstance(payload, dict)
        or payload.get("error")
        or not isinstance(payload.get("daily"), dict)
        or not isinstance(payload["daily"].get("time"), list)
    ):
        reason = _safe_provider_reason(payload)
        logger.warning(
            "Open-Meteo %s returned an invalid payload: %s",
            provider, reason or "missing daily time series",
        )
        raise WeatherProviderError(f"Open-Meteo {provider}: invalid data")

    with _CACHE_LOCK:
        if len(_CACHE) >= _CACHE_MAX_ENTRIES:
            _CACHE.clear()
        _CACHE[key] = (now + (21_600 if provider == "archive" else 900), payload)
    return payload


def _fetch_weather(*, archive: bool, params: dict) -> dict:
    """Compatibility wrapper for public historical + near-term model calls."""
    return _request_provider(
        provider="archive" if archive else "forecast",
        params=params,
    )


def _fetch_historical_forecast(params: dict) -> dict:
    """Alternative *modeled* historical dataset, never mislabeled reanalysis."""
    return _request_provider(provider="historical_forecast", params=params)


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _hourly_humidity(payload: dict) -> dict[date, float]:
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        return {}
    timestamps = hourly.get("time")
    values = hourly.get("relative_humidity_2m")
    if not isinstance(timestamps, list) or not isinstance(values, list):
        return {}
    bucket: dict[date, list[float]] = defaultdict(list)
    for timestamp, value in zip(timestamps, values):
        if not isinstance(timestamp, str):
            continue
        try:
            hour_date = date.fromisoformat(timestamp[:10])
        except ValueError:
            continue
        humidity = _number(value)
        if humidity is not None:
            bucket[hour_date].append(humidity)

    # Avoid treating a few partial hours as the mean of the entire day.
    return {
        day: round(sum(items) / len(items), 1)
        for day, items in bucket.items()
        if len(items) >= 23
    }


def _parse_daily(payload: dict, source: str, *, today: date) -> list[WeatherDay]:
    daily = payload.get("daily", {})
    dates = daily.get("time", [])
    if not isinstance(dates, list):
        raise WeatherProviderError("Weather provider returned malformed dates.")
    derived_humidity = _hourly_humidity(payload)
    results = []
    for index, date_str in enumerate(dates):
        try:
            day = date.fromisoformat(date_str)
        except (TypeError, ValueError) as exc:
            raise WeatherProviderError("Weather provider returned an invalid date.") from exc
        day_source = "forecast" if source == "recent_model" and day > today else source
        values = {}
        for target, upstream in FIELD_MAP.items():
            readings = daily.get(upstream)
            values[target] = (
                _number(readings[index])
                if isinstance(readings, list) and index < len(readings)
                else None
            )
        if values["relative_humidity_mean_percent"] is None:
            values["relative_humidity_mean_percent"] = derived_humidity.get(day)
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

    archive_end = min(end_date, today - timedelta(days=8))
    newest_start = today - timedelta(days=7)
    forecast_end = today + timedelta(days=6) if include_forecast else None
    records: dict[date, WeatherDay] = {}
    warnings: list[str] = []
    timezone_name = "auto"
    base = {"latitude": round(latitude, 5), "longitude": round(longitude, 5)}

    if start_date <= archive_end:
        bounds = {
            **base,
            "start_date": start_date.isoformat(),
            "end_date": archive_end.isoformat(),
        }
        try:
            historical = _fetch_weather(archive=True, params=bounds)
            timezone_name = str(historical.get("timezone") or timezone_name)
            for entry in _parse_daily(historical, "historical", today=today):
                if start_date <= entry.date <= end_date:
                    records[entry.date] = entry
        except WeatherProviderError as exc:
            logger.warning("Historical reanalysis unavailable: %s", exc)
            warnings.append("Historical reanalysis is unavailable; trying archived forecasts.")
            if start_date >= date(2022, 1, 1):
                try:
                    fallback = _fetch_historical_forecast(bounds)
                    timezone_name = str(fallback.get("timezone") or timezone_name)
                    for entry in _parse_daily(fallback, "historical_forecast", today=today):
                        if start_date <= entry.date <= archive_end:
                            records[entry.date] = entry
                    warnings.append(
                        "Historical forecast models were used as fallback; they are not ERA5 reanalysis."
                    )
                except WeatherProviderError as fallback_error:
                    logger.warning("Historical forecast fallback unavailable: %s", fallback_error)
                    warnings.append("Historical forecast backup is also unavailable.")
            else:
                warnings.append("Archived forecast fallback is only supported from 2022 onward.")

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
                    records.setdefault(entry.date, entry)
        except WeatherProviderError as exc:
            logger.warning("Recent forecast API unavailable: %s", exc)
            warnings.append("Recent modeled weather and forecast are temporarily unavailable.")

    if not records:
        logger.warning(
            "No weather data: archive and recent model sources could not cover requested dates."
        )
        raise WeatherProviderError(
            "No weather data is available for the selected field and dates. "
            "Check API server logs for Open-Meteo provider errors."
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
