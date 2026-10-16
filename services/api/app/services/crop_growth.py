"""Build crop phenology context without claiming a crop diagnosis."""
from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from app.models.crop_cycle import CropCycle
from app.models.crop_stage_observation import CropStageObservation
from app.schemas.crop_growth import CropGrowthResponse, StageDefinition
from app.domains.crops.phenology import (
    growing_degree_days,
    bbch_family,
    provisional_stage,
    resolve_profile,
)
from app.services.weather import WeatherProviderError, load_field_weather


def make_crop_growth_response(
    *,
    crop_cycle: CropCycle,
    observations: list[CropStageObservation],
    latitude: float,
    longitude: float,
    today: date,
) -> CropGrowthResponse:
    profile = resolve_profile(crop_cycle.crop_name)
    planted = crop_cycle.planted_on
    as_of = min(today, crop_cycle.harvested_on or today)
    age = (as_of - planted).days if planted and planted <= as_of else None
    warnings: list[str] = []
    estimate = provisional_stage(
        crop_name=crop_cycle.crop_name, planted_on=planted, as_of=as_of
    )
    if not planted:
        warnings.append("Enter a planting date to enable provisional stages and GDD.")
    if profile.key in {"mango", "litchi", "guava", "sapota"}:
        warnings.append("Orchard development is recorded manually; this service does not predict flowering or fruiting dates.")
    if profile.key == "other":
        warnings.append("No stage calendar is calibrated for this crop. Record actual stages manually.")
    elif estimate:
        warnings.append("Stage estimate uses broad days-after-planting milestones, not a validated local cultivar model.")

    accumulated = None
    available = expected = 0
    if planted and planted <= as_of and profile.base_temperature_c is not None:
        period = (as_of - planted).days
        if period > 365:
            warnings.append("Planting-to-current period exceeds weather request limits; GDD was not estimated.")
        else:
            try:
                weather = load_field_weather(
                    field_id=crop_cycle.field_id,
                    latitude=latitude,
                    longitude=longitude,
                    start_date=planted,
                    end_date=as_of,
                    include_forecast=False,
                )
                accumulated, available, expected = growing_degree_days(
                    planted_on=planted,
                    as_of=as_of,
                    base_temperature_c=profile.base_temperature_c,
                    daily_readings=weather.days,
                )
                if accumulated is None:
                    warnings.append(
                        f"GDD unavailable: {available} of {expected} modeled-temperature days covered."
                    )
                if weather.warnings:
                    warnings.extend(weather.warnings)
            except WeatherProviderError:
                warnings.append("Weather unavailable; growth-stage records remain available without GDD.")

    chronological = sorted(observations, key=lambda entry: (entry.observed_on, entry.created_at))
    latest_recorded = chronological[-1].stage_code if chronological else None

    return CropGrowthResponse(
        crop_cycle_id=crop_cycle.id,
        crop_name=crop_cycle.crop_name,
        profile_key=profile.key,
        profile_version=profile.version,
        planting_date=planted,
        as_of=as_of,
        days_after_planting=age,
        stages=[
            StageDefinition(
                code=stage.code,
                label=stage.label,
                approx_days_after_planting=stage.approx_day,
                bbch_reference=bbch_family(profile.key, stage.code),
            ) for stage in profile.stages
        ],
        observations=chronological,
        latest_recorded_stage=latest_recorded,
        provisional_stage=estimate,
        degree_day_base_c=profile.base_temperature_c,
        accumulated_gdd_c_days=accumulated,
        gdd_days_available=available,
        gdd_days_expected=expected,
        warnings=warnings,
    )
