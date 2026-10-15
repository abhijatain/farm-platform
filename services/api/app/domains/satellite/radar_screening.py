"""Explainable same-orbit, same-stage radar screening.

Avoid false comparisons across orbit geometry, uncertain growth stages,
cloud invalid data and arbitrary published 'crop health' interpretations.
Thresholds are conservative engineering heuristics, NOT agronomic
calibrations. Screen only, not an operational alert system.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta
from statistics import median
from uuid import UUID

from app.schemas.radar_screening import (
    CropRadarScreeningResponse,
    RadarOpticalContext,
    RadarOrbitScreen,
    RadarScreenMetric,
    RadarWeatherContext,
)
from app.schemas.satellite_trends import FieldSatelliteTrendsResponse, SatelliteTrendPoint
from app.schemas.weather import WeatherDay
from app.domains.crops.phenology import provisional_stage, resolve_profile


SCREEN_METRICS = ("sar_vh_db", "sar_vv_db", "sar_rvi")
OPTICAL_METRICS = ("ndvi", "ndmi")
ABSOLUTE_FLOORS = {"sar_vh_db": 1.5, "sar_vv_db": 1.5, "sar_rvi": 0.15}
UNITS = {"sar_vh_db": "dB", "sar_vv_db": "dB", "sar_rvi": "index"}
MIN_BASELINE = 3
COVERAGE_MIN = 80.0
# Conservative modifiers are screening guardrails, not clinical/agronomic rules.
CROP_MULTIPLIER = {"rice": 1.25, "wheat": 1.0, "maize": 1.15}
STAGE_MULTIPLIER = {
    "planting": 1.5, "establishment": 1.5, "emergence": 1.5,
    "vegetative": 1.3, "stem_elongation": 1.2,
    "panicle": 1.2, "tasseling": 1.2, "silking": 1.2,
    "heading": 1.1, "flowering": 1.1,
    "grain_fill": 1.1, "fruiting": 1.1, "maturity": 1.1,
}


def _valid(point: SatelliteTrendPoint) -> bool:
    return (
        point.median is not None
        and math.isfinite(point.median)
        and point.valid_pixel_percent is not None
        and math.isfinite(point.valid_pixel_percent)
        and point.valid_pixel_percent >= COVERAGE_MIN
    )


def stage_at(
    *,
    crop_name: str,
    planted_on: date | None,
    as_of: date,
    observations: list,
) -> tuple[str | None, str]:
    """A confirmed transition applies only from its recorded date onward."""
    profile = resolve_profile(crop_name)
    order = {item.code: i for i, item in enumerate(profile.stages)}
    confirmed = [
        item for item in observations
        if item.observed_on <= as_of and item.stage_code in order
    ]
    if confirmed:
        latest = max(confirmed, key=lambda x: (x.observed_on, order[x.stage_code]))
        return latest.stage_code, "farmer_confirmed"
    estimate = provisional_stage(
        crop_name=crop_name,
        planted_on=planted_on,
        as_of=as_of,
    )
    return (estimate, "provisional") if estimate else (None, "unknown")


def _weather_context(
    *,
    observed_on: date,
    days: list[WeatherDay],
) -> RadarWeatherContext:
    # Require all three local calendar days. Incomplete windows are unknown.
    wanted = {observed_on - timedelta(days=n) for n in range(3)}
    values = {
        item.date: item.precipitation_mm
        for item in days
        if item.date in wanted
        and item.source != "forecast"
        and item.precipitation_mm is not None
        and math.isfinite(item.precipitation_mm)
        and item.precipitation_mm >= 0
    }
    total = round(sum(values.values()), 1) if len(values) == 3 else None
    return RadarWeatherContext(
        precipitation_3_day_mm=total,
        days_available=len(values),
        wet_weather_context=None if total is None else total >= 10,
    )


def _optical_context(*, date_of_radar: date, points: list[SatelliteTrendPoint]) -> list[RadarOpticalContext]:
    results = []
    for metric in OPTICAL_METRICS:
        candidates = [
            p for p in points
            if p.metric_type == metric
            and _valid(p)
            and 0 <= (date_of_radar - p.observed_on).days <= 10
            and not p.source.startswith("sentinel-1")
        ]
        if candidates:
            closest = max(candidates, key=lambda p: p.observed_on)
            results.append(RadarOpticalContext(
                metric_type=metric,
                observed_on=closest.observed_on,
                value=round(closest.median, 3),
                days_from_radar=(date_of_radar - closest.observed_on).days,
            ))
    return results


def _screen_metric(
    *,
    metric_type: str,
    latest: SatelliteTrendPoint,
    earlier: list[SatelliteTrendPoint],
    stage_code: str | None,
    stage_source: str,
    crop_key: str,
) -> RadarScreenMetric:
    baseline_values = [p.median for p in earlier]
    count = len(baseline_values)
    args = dict(
        metric_type=metric_type,
        unit=UNITS[metric_type],
        latest_value=round(latest.median, 3),
        baseline_passes=count,
    )
    if stage_source != "farmer_confirmed":
        return RadarScreenMetric(status="unverified_stage", **args)
    if crop_key == "other":
        return RadarScreenMetric(status="unsupported_crop", **args)
    if count < MIN_BASELINE:
        return RadarScreenMetric(status="insufficient_baseline", **args)

    ref = median(baseline_values)
    absolute_deviations = [abs(value - ref) for value in baseline_values]
    mad = median(absolute_deviations)
    multiplier = (
        CROP_MULTIPLIER.get(crop_key, 1.3)
        * STAGE_MULTIPLIER.get(stage_code, 1.25)
    )
    threshold = max(
        ABSOLUTE_FLOORS[metric_type] * multiplier,
        3.0 * 1.4826 * mad * multiplier,
    )
    deviation = latest.median - ref
    return RadarScreenMetric(
        status=(
            "unusual_variation" if abs(deviation) > threshold
            else "within_reference_range"
        ),
        reference_median=round(ref, 3),
        difference=round(deviation, 3),
        screening_threshold=round(threshold, 3),
        **args,
    )


def build_radar_screening(
    *,
    crop_cycle_id: UUID,
    field_id: UUID,
    crop_name: str,
    planted_on: date | None,
    as_of: date,
    stage_observations: list,
    trends: FieldSatelliteTrendsResponse,
    weather_days: list[WeatherDay],
    weather_warnings: list[str] | None = None,
) -> CropRadarScreeningResponse:
    profile = resolve_profile(crop_name)
    warnings = list(weather_warnings or [])
    if not stage_observations:
        warnings.append("No farmer-confirmed growth-stage dates. Automatic unusual-variation screening is withheld.")
    if not planted_on:
        warnings.append("Planting date is absent. Provisional stages are unavailable.")
    if profile.key == "other":
        warnings.append("Unknown crop profile: crop-calibrated thresholds are unavailable; manual stages can still be recorded.")

    by_orbit: dict[str, list[SatelliteTrendPoint]] = defaultdict(list)
    for p in trends.points:
        if (
            p.source.startswith("sentinel-1")
            and p.metric_type in SCREEN_METRICS
            and p.radar_orbit_key
            and p.orbit_state in ("ascending", "descending")
            and p.relative_orbit is not None
            and p.radar_orbit_key == f"{p.orbit_state}:{p.relative_orbit}"
            and p.observed_on <= as_of
            and _valid(p)
        ):
            by_orbit[p.radar_orbit_key].append(p)

    orbits: list[RadarOrbitScreen] = []
    for key, radar_points in sorted(by_orbit.items()):
        radar_points.sort(key=lambda p: (p.observed_on, str(p.observation_id)))
        latest_date = max(p.observed_on for p in radar_points)
        latest_stage, stage_source = stage_at(
            crop_name=crop_name,
            planted_on=planted_on,
            as_of=latest_date,
            observations=stage_observations,
        )
        # Choose latest observation *within* the orbit, not latest metric from
        # a different scene; a candidate scene needs at least one valid metric.
        last_observation = max(
            radar_points,
            key=lambda p: (p.observed_on, str(p.observation_id)),
        )
        latest_obs_id = last_observation.observation_id
        current_points = {
            p.metric_type: p for p in radar_points
            if p.observation_id == latest_obs_id
        }
        metrics: list[RadarScreenMetric] = []
        for metric_type in SCREEN_METRICS:
            current = current_points.get(metric_type)
            if current is None:
                continue
            prior = [
                p for p in radar_points
                if p.metric_type == metric_type
                and p.observed_on < latest_date
                and p.observation_id != latest_obs_id
                and (latest_date - p.observed_on).days <= 120
                and stage_at(
                    crop_name=crop_name, planted_on=planted_on,
                    as_of=p.observed_on, observations=stage_observations,
                ) == (latest_stage, stage_source)
            ]
            prior.sort(key=lambda p: p.observed_on, reverse=True)
            # Exclude duplicated same-day scenes as independent baselines.
            by_day = {}
            for point in prior:
                by_day.setdefault(point.observed_on, point)
            metrics.append(_screen_metric(
                metric_type=metric_type, latest=current,
                earlier=list(by_day.values())[:8],
                stage_code=latest_stage,
                stage_source=stage_source,
                crop_key=profile.key,
            ))

        weather = _weather_context(observed_on=latest_date, days=weather_days)
        optical = _optical_context(date_of_radar=latest_date, points=trends.points)
        activities = [
            item.activity_type
            for item in trends.activities
            if (
                item.crop_cycle_id == crop_cycle_id
                and 0 <= (latest_date - item.occurred_at.date()).days <= 5
            )
        ]
        unusual = any(x.status == "unusual_variation" for x in metrics)
        has_screen = any(x.status in ("unusual_variation", "within_reference_range") for x in metrics)
        explanations: list[str] = []
        if stage_source == "farmer_confirmed" and profile.key == "other":
            explanations.append(
                "This crop has no supported radar screening profile. Confirmed stages are recorded, but variation flags are withheld until a crop-specific configuration is validated."
            )
        elif stage_source != "farmer_confirmed":
            explanations.append(
                "The acquisition does not have a farmer-confirmed growth stage; only descriptive measurements are available."
            )
        elif not has_screen:
            explanations.append(
                "At least three earlier valid passes from this orbit and confirmed growth stage are required."
            )
        elif unusual:
            explanations.append(
                "One or more field-median radar metrics exceed conservative same-stage historical-variation thresholds. Investigate; this does not identify a cause."
            )
        else:
            explanations.append("Screened metric values did not exceed the heuristic variation thresholds.")
        if weather.wet_weather_context:
            explanations.append("At least 10 mm modeled rain fell during the 3-day acquisition window; moisture may affect radar backscatter.")
        elif weather.precipitation_3_day_mm is None:
            explanations.append("The preceding 3-day rainfall window is incomplete; weather influence is unknown.")
        if not optical:
            explanations.append("No sufficiently covered optical NDVI/NDMI reading within the prior 10 days.")
        if activities:
            explanations.append("Recorded farm activity occurred within five days of the radar acquisition.")
        stage_label = next(
            (s.label for s in profile.stages if s.code == latest_stage),
            None,
        )
        orbits.append(RadarOrbitScreen(
            radar_orbit_key=key,
            orbit_state=last_observation.orbit_state,
            relative_orbit=last_observation.relative_orbit,
            platform=last_observation.platform,
            observed_on=latest_date,
            stage_code=latest_stage,
            stage_label=stage_label,
            stage_source=stage_source,
            status=(
                "review_variation" if unusual else
                "within_reference_range" if has_screen else
                "insufficient_evidence"
            ),
            metrics=metrics,
            weather=weather,
            optical=optical,
            nearby_activities=sorted(set(activities)),
            explanations=explanations,
        ))

    if not orbits:
        warnings.append("No orbit-comparable radar measurements with at least 80% valid coverage are available.")
    return CropRadarScreeningResponse(
        crop_cycle_id=crop_cycle_id,
        field_id=field_id,
        crop_name=crop_name,
        profile_key=profile.key,
        as_of=as_of,
        orbits=orbits,
        warnings=warnings,
    )
