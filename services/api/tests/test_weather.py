"""Check modeled weather parsing, coverage, errors and fallback provenance."""

from datetime import date, timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.services.weather import (
    WeatherProviderError,
    _parse_daily,
    load_field_weather,
)


TODAY = date(2026, 10, 15)


def _payload(days, *, precipitation=2.5):
    return {
        "timezone": "Asia/Kolkata",
        "daily": {
            "time": [day.isoformat() for day in days],
            "precipitation_sum": [precipitation] * len(days),
            "temperature_2m_max": [32.0] * len(days),
            "temperature_2m_min": [22.0] * len(days),
            "relative_humidity_2m_mean": [65.0] * len(days),
            "wind_speed_10m_max": [14.0] * len(days),
            "et0_fao_evapotranspiration": [4.1] * len(days),
            "weather_code": [3] * len(days),
        },
    }


def test_daily_parser_preserves_null_rain_and_marks_forecasts():
    days = [TODAY - timedelta(days=1), TODAY + timedelta(days=1)]
    payload = _payload(days)
    payload["daily"]["precipitation_sum"] = [None, 5.0]

    points = _parse_daily(payload, "recent_model", today=TODAY)

    assert points[0].source == "recent_model"
    assert points[0].precipitation_mm is None
    assert points[1].source == "forecast"
    assert points[1].precipitation_mm == 5.0


def test_combines_archive_recent_and_forecast_without_overlap():
    first = TODAY - timedelta(days=12)
    older = [first + timedelta(days=i) for i in range(5)]
    recent_days = [TODAY - timedelta(days=7) + timedelta(days=i) for i in range(14)]
    calls = []

    def fake_fetch(*, archive, params):
        calls.append((archive, params))
        return _payload(older if archive else recent_days, precipitation=1.5 if archive else 7.0)

    with patch("app.services.weather._today", return_value=TODAY), patch(
        "app.services.weather._fetch_weather", side_effect=fake_fetch
    ):
        result = load_field_weather(
            field_id=uuid4(),
            latitude=30.72,
            longitude=76.72,
            start_date=first,
            end_date=TODAY,
        )

    assert len(calls) == 2
    assert len(result.days) == 19
    assert result.days[0].source == "historical"
    assert result.days[-1].source == "forecast"
    assert result.days[-1].date == TODAY + timedelta(days=6)
    assert result.days[0].precipitation_mm == 1.5
    assert result.timezone == "Asia/Kolkata"


def test_missing_weather_source_raises_not_false_zero():
    with patch("app.services.weather._today", return_value=TODAY), patch(
        "app.services.weather._fetch_weather",
        side_effect=WeatherProviderError("offline"),
    ):
        with pytest.raises(WeatherProviderError, match="No weather data"):
            load_field_weather(
                field_id=uuid4(),
                latitude=30.72,
                longitude=76.72,
                start_date=TODAY - timedelta(days=2),
                end_date=TODAY,
            )


def test_archive_error_returns_recent_weather_with_warning():
    recent_days = [TODAY - timedelta(days=i) for i in range(7)]

    def fetch(*, archive, params):
        if archive:
            raise WeatherProviderError("offline")
        return _payload(recent_days)

    with patch("app.services.weather._today", return_value=TODAY), patch(
        "app.services.weather._fetch_weather", side_effect=fetch
    ), patch(
        "app.services.weather._fetch_historical_forecast",
        side_effect=WeatherProviderError("fallback offline"),
    ):
        result = load_field_weather(
            field_id=uuid4(),
            latitude=30.72,
            longitude=76.72,
            start_date=TODAY - timedelta(days=30),
            end_date=TODAY,
            include_forecast=False,
        )
    assert result.days
    assert not any(day.source == "historical" for day in result.days)
    assert result.warnings


@pytest.mark.parametrize("start,end", [
    (TODAY, TODAY - timedelta(days=1)),
    (TODAY - timedelta(days=370), TODAY),
    (TODAY, TODAY + timedelta(days=2)),
])
def test_invalid_dates_rejected(start, end):
    with patch("app.services.weather._today", return_value=TODAY):
        with pytest.raises(ValueError):
            load_field_weather(
                field_id=uuid4(),
                latitude=30.72,
                longitude=76.72,
                start_date=start,
                end_date=end,
            )


def test_history_does_not_request_future_when_disabled():
    older = TODAY - timedelta(days=40)
    with patch("app.services.weather._today", return_value=TODAY), patch(
        "app.services.weather._fetch_weather", return_value=_payload([older])
    ) as fetch:
        result = load_field_weather(
            field_id=uuid4(),
            latitude=30.72,
            longitude=76.72,
            start_date=older,
            end_date=older,
            include_forecast=False,
        )
    fetch.assert_called_once()
    assert result.forecast_end_date is None
    assert len(result.days) == 1
    assert result.days[0].source == "historical"



def test_archive_fallback_labeled_and_has_growth_temperature_history():
    first = TODAY - timedelta(days=12)
    older = [first + timedelta(days=i) for i in range(5)]
    recent_days = [TODAY - timedelta(days=7) + timedelta(days=i) for i in range(14)]

    def fake_fetch(*, archive, params):
        if archive:
            raise WeatherProviderError("Open-Meteo archive: HTTP 503")
        return _payload(recent_days, precipitation=3.0)

    with patch("app.services.weather._today", return_value=TODAY), patch(
        "app.services.weather._fetch_weather", side_effect=fake_fetch
    ), patch(
        "app.services.weather._fetch_historical_forecast",
        return_value=_payload(older, precipitation=1.5),
    ) as fallback:
        result = load_field_weather(
            field_id=uuid4(), latitude=30.72, longitude=76.72,
            start_date=first, end_date=TODAY,
        )

    fallback.assert_called_once()
    assert len(result.days) == 19
    assert result.days[0].source == "historical_forecast"
    assert result.days[0].temperature_max_c == 32.0
    assert result.days[-1].source == "forecast"
    assert any("not ERA5 reanalysis" in message for message in result.warnings)


def test_forecast_humidity_uses_hourly_values():
    days = [TODAY, TODAY + timedelta(days=1)]
    response = _payload(days)
    response["daily"].pop("relative_humidity_2m_mean")
    response["hourly"] = {
        "time": [
            (TODAY + timedelta(days=day_index)).isoformat() + f"T{hour:02}:00"
            for day_index in range(2) for hour in range(24)
        ],
        "relative_humidity_2m": [60.0] * 24 + [80.0] * 24,
    }
    items = _parse_daily(response, "recent_model", today=TODAY)
    assert items[0].relative_humidity_mean_percent == 60.0
    assert items[1].relative_humidity_mean_percent == 80.0


def test_incomplete_hourly_humidity_is_not_treated_as_full_day():
    response = _payload([TODAY])
    response["daily"].pop("relative_humidity_2m_mean")
    response["hourly"] = {
        "time": [f"{TODAY.isoformat()}T{i:02}:00" for i in range(3)],
        "relative_humidity_2m": [99, 97, 98],
    }
    item = _parse_daily(response, "recent_model", today=TODAY)[0]
    assert item.relative_humidity_mean_percent is None



def test_provider_uses_supported_forecast_humidity_parameters():
    import json
    from unittest.mock import MagicMock
    from urllib.parse import parse_qs, urlparse

    from app.services.weather import _request_provider

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *unused):
            return None

        def read(self, limit):
            return json.dumps(_payload([TODAY])).encode("utf-8")

    with patch("app.services.weather._has_api_key", return_value=False), patch(
        "app.services.weather.urlopen", return_value=FakeResponse()
    ) as open_url:
        data = _request_provider(
            provider="forecast",
            params={"latitude": 15.12345, "longitude": 70.56789, "past_days": 7, "forecast_days": 7},
        )

    assert "daily" in data
    requested = open_url.call_args.args[0]
    query = parse_qs(urlparse(requested.full_url).query)
    assert "relative_humidity_2m_mean" not in query["daily"][0]
    assert "relative_humidity_2m" in query["hourly"][0]


def test_open_meteo_400_error_exposes_status_without_request_url():
    import io
    from urllib.error import HTTPError

    from app.services.weather import _request_provider

    invalid = HTTPError(
        "https://api.open-meteo.com/?apikey=SECRET_DO_NOT_PRINT",
        400, "bad request", {}, io.BytesIO(b'{"error":true,"reason":"Invalid daily variable"}'),
    )
    with patch("app.services.weather._has_api_key", return_value=False), patch(
        "app.services.weather.urlopen", side_effect=invalid
    ):
        with pytest.raises(WeatherProviderError, match="HTTP 400") as raised:
            _request_provider(
                provider="forecast",
                params={"latitude": 15.124, "longitude": 70.568, "past_days": 7},
            )
    assert "Invalid daily variable" in str(raised.value)
    assert "SECRET_DO_NOT_PRINT" not in str(raised.value)
