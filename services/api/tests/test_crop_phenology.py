"""Validate provisional crop calendars and complete GDD coverage."""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.schemas.crop_growth import StageObservationInput
from app.schemas.weather import WeatherDay
from app.services.crop_phenology import (
    growing_degree_days,
    provisional_stage,
    resolve_profile,
)
from app.services.crop_growth import make_crop_growth_response
from app.services.weather import WeatherProviderError


def test_profiles_support_local_aliases_and_manual_only_unknowns():
    assert resolve_profile(" Gehun ").key == "wheat"
    assert resolve_profile("dhan").key == "rice"
    assert resolve_profile("MAKKA").key == "maize"
    unknown = resolve_profile("Guava")
    assert unknown.key == "other"
    assert not unknown.provisional
    assert all(stage.approx_day is None for stage in unknown.stages)


def test_provisional_stage_requires_real_planting_date():
    today = date(2026, 10, 15)
    assert provisional_stage(crop_name="wheat", planted_on=None, as_of=today) is None
    assert provisional_stage(crop_name="wheat", planted_on=today + timedelta(days=1), as_of=today) is None
    assert provisional_stage(crop_name="Guava", planted_on=today - timedelta(days=40), as_of=today) is None
    assert provisional_stage(crop_name="wheat", planted_on=today - timedelta(days=30), as_of=today) == "vegetative"
    assert provisional_stage(crop_name="rice", planted_on=today - timedelta(days=95), as_of=today) == "heading"


def _temperatures(day, min_value=20.0, max_value=30.0, source="historical"):
    return WeatherDay(
        date=day, source=source,
        temperature_min_c=min_value, temperature_max_c=max_value,
        precipitation_mm=None,
    )


def test_gdd_all_days_required_and_negative_dd_clamped():
    start = date(2026, 10, 10)
    days = [_temperatures(start + timedelta(days=i)) for i in range(3)]
    total, available, expected = growing_degree_days(
        planted_on=start, as_of=start + timedelta(days=2),
        base_temperature_c=10, daily_readings=days,
    )
    assert (total, available, expected) == (45.0, 3, 3)

    days[1] = _temperatures(start + timedelta(days=1), 5.0, 7.0)
    assert growing_degree_days(
        planted_on=start, as_of=start + timedelta(days=2),
        base_temperature_c=10, daily_readings=days,
    )[0] == 30.0

    assert growing_degree_days(
        planted_on=start, as_of=start + timedelta(days=2),
        base_temperature_c=10, daily_readings=days[:2],
    ) == (None, 2, 3)


def test_forecast_temperature_never_counts_toward_gdd():
    start = date(2026, 10, 10)
    readings = [
        _temperatures(start),
        _temperatures(start + timedelta(days=1), source="forecast"),
    ]
    assert growing_degree_days(
        planted_on=start, as_of=start + timedelta(days=1),
        base_temperature_c=10, daily_readings=readings,
    ) == (None, 1, 2)


def test_stage_input_validates_code_and_notes():
    with pytest.raises(ValidationError):
        StageObservationInput(stage_code="", observed_on=date.today())
    with pytest.raises(ValidationError):
        StageObservationInput(stage_code="heading", observed_on=date.today(), notes="x" * 2001)


def test_growth_response_survives_weather_provider_outage():
    today = date(2026, 10, 15)
    cycle = SimpleNamespace(
        id=uuid4(), field_id=uuid4(), crop_name="wheat",
        planted_on=today - timedelta(days=45), harvested_on=None,
    )
    with patch("app.services.crop_growth.load_field_weather", side_effect=WeatherProviderError("offline")):
        result = make_crop_growth_response(
            crop_cycle=cycle, observations=[], latitude=30.72,
            longitude=76.7, today=today,
        )
    assert result.provisional_stage == "vegetative"
    assert result.accumulated_gdd_c_days is None
    assert result.observations == []
    assert any("Weather unavailable" in warning for warning in result.warnings)


def test_manual_stages_remain_separate_from_provisional_estimate():
    today = date(2026, 10, 15)
    cycle = SimpleNamespace(
        id=uuid4(), field_id=uuid4(), crop_name="wheat",
        planted_on=None, harvested_on=None,
    )
    observed = SimpleNamespace(
        id=uuid4(), crop_cycle_id=cycle.id, stage_code="emergence",
        observed_on=today - timedelta(days=10), notes="First shoots",
        created_at=datetime(2026, 10, 5, tzinfo=timezone.utc),
        updated_at=datetime(2026, 10, 5, tzinfo=timezone.utc),
    )
    result = make_crop_growth_response(
        crop_cycle=cycle, observations=[observed],
        latitude=30.72, longitude=76.7, today=today,
    )
    assert result.latest_recorded_stage == "emergence"
    assert result.provisional_stage is None
    assert result.accumulated_gdd_c_days is None
    assert any("Enter a planting date" in warning for warning in result.warnings)
