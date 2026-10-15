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
    assert len(result.days) == 20
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
