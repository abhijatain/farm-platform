"""Owner-scoped, quality-gated historical zones, radar, optical and phenology."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select, text

from app.api.deps import DBSession, CurrentUser
from app.domains.crops.phenology import resolve_profile, provisional_stage
from app.domains.satellite.field_intelligence import (
    build_field_comparisons, indices_for_stage, quality_ok,
)
from app.domains.satellite.spatial_history import Scene, summarize_spatial_history
from app.domains.satellite.trends import get_field_satellite_trends
from app.models.crop_cycle import CropCycle
from app.models.crop_stage_observation import CropStageObservation
from app.models.field import Field
from app.models.satellite_anomaly import SatelliteAnomaly
from app.models.satellite_metric import SatelliteMetric
from app.models.satellite_observation import SatelliteObservation
from app.services.ownership import get_owned_field, get_owned_crop_cycle
from app.services.weather import _today

from shapely.geometry import shape
from shapely.ops import unary_union

router = APIRouter(tags=["field intelligence"])
MAX_MONTHS = 132
MAX_RECENT = 4
MAX_ANOMALIES = 1200


@router.get("/fields/{field_id}/spatial-history")
def spatial_history(
    field_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    metric_type: str = Query(default="ndvi", pattern="^(ndvi|ndmi|ndre)$"),
    years: int = Query(default=10, ge=1, le=10),
) -> dict:
    """Relative below/above-field-baseline exposure, not measured yield zones."""
    get_owned_field(db=db, user_id=current_user.id, field_id=field_id)
    geom_json, real_area = db.execute(
        text("SELECT ST_AsGeoJSON(ST_Transform(boundary, 3857)), "
             "ST_Area(boundary::geography) FROM fields WHERE id = :id"),
        {"id": field_id},
    ).one()
    geom = shape(json.loads(geom_json))
    cutoff = _today() - timedelta(days=365 * years + 3)
    # Balanced monthly samples retain the entire 10-year window instead of
    # allowing the latest dense year to crowd all older observations out.
    # A few additional recent scenes preserve short-date anomaly transitions.
    monthly_bucket = func.date_trunc("month", SatelliteObservation.observed_on)
    qualified = (
        select(SatelliteObservation, SatelliteMetric)
        .join(SatelliteMetric, SatelliteMetric.satellite_observation_id == SatelliteObservation.id)
        .where(
            SatelliteObservation.field_id == field_id,
            SatelliteObservation.source == "sentinel-2",
            SatelliteObservation.observed_on >= cutoff,
            SatelliteObservation.observed_on <= _today(),
            SatelliteMetric.metric_type == metric_type,
            SatelliteMetric.valid_pixel_percent >= 80.0,
            SatelliteMetric.valid_pixel_count >= 8,
        )
    )
    monthly = db.execute(
        qualified.distinct(monthly_bucket).order_by(
            monthly_bucket.desc(),
            SatelliteMetric.valid_pixel_percent.desc(),
            SatelliteObservation.observed_on.desc(),
        ).limit(MAX_MONTHS + 1)
    ).all()
    recent = db.execute(
        qualified.order_by(
            SatelliteObservation.observed_on.desc(),
            SatelliteMetric.valid_pixel_percent.desc(),
        ).limit(MAX_RECENT)
    ).all()
    limited = len(monthly) > MAX_MONTHS
    dates = set()
    selected = []
    for observation, metric in [*recent, *monthly[:MAX_MONTHS]]:
        if observation.observed_on in dates:
            continue
        dates.add(observation.observed_on)
        selected.append((observation, metric))
    selected.sort(key=lambda pair: pair[0].observed_on, reverse=True)
    if not selected:
        result = summarize_spatial_history(geom, float(real_area), [])
        result["warnings"].append("No suitable optical date has >=80% valid coverage and >=8 valid pixels.")
        result.update({"field_id": str(field_id), "metric_type": metric_type, "history_years": years, "sampling": "monthly_best_plus_recent_4"})
        return result
    ids = [observation.id for observation, _ in selected]
    shapes = db.execute(
        select(
            SatelliteAnomaly.satellite_observation_id,
            SatelliteAnomaly.anomaly_type,
            func.ST_AsGeoJSON(func.ST_Transform(SatelliteAnomaly.geometry, 3857)),
        )
        .where(
            SatelliteAnomaly.satellite_observation_id.in_(ids),
            SatelliteAnomaly.index_type == metric_type,
            SatelliteAnomaly.anomaly_type.in_(
                ("below_field_baseline", "above_field_baseline")
            ),
        ).limit(MAX_ANOMALIES + 1)
    ).all()
    limited = limited or len(shapes) > MAX_ANOMALIES
    by_scene = defaultdict(lambda: defaultdict(list))
    for scene_id, category, geom_text in shapes[:MAX_ANOMALIES]:
        try:
            polygon = shape(json.loads(geom_text))
            if polygon.is_valid and polygon.area > 0:
                by_scene[scene_id][category].append(polygon)
        except (ValueError, TypeError):
            continue
    scenes = []
    for observation, metric in selected:
        unions = {
            key: unary_union(polygons).intersection(geom)
            for key, polygons in by_scene[observation.id].items()
        }
        scenes.append(Scene(
            observation_id=str(observation.id),
            observed_on=observation.observed_on,
            valid_percent=metric.valid_pixel_percent,
            native_resolution_m=metric.output_resolution_m or metric.native_resolution_m or 20.0,
            polygons=unions,
        ))
    result = summarize_spatial_history(
        geom, float(real_area), scenes, history_limited=limited,
    )
    result.update({"field_id": str(field_id), "metric_type": metric_type, "history_years": years, "sampling": "monthly_best_plus_recent_4"})
    if limited:
        result["warnings"].append("More than the bounded query limit was available; extend analysis offline.")
    return result


@router.get("/fields/{field_id}/observation-intelligence")
def observation_intelligence(
    field_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    years: int = Query(default=2, ge=1, le=10),
) -> dict:
    """Plain-language two-pass optical/same-orbit radar deltas and quality."""
    get_owned_field(db=db, user_id=current_user.id, field_id=field_id)
    end = _today()
    trends = get_field_satellite_trends(
        db=db, field_id=field_id, crop_cycle=None,
        start_date=end - timedelta(days=years * 365 + 2),
        end_date=end,
    )
    summary = build_field_comparisons(trends.points)
    return {"field_id": str(field_id), "window_years": years, **summary}


@router.get("/crop-cycles/{crop_cycle_id}/phenology-intelligence")
def phenology_intelligence(
    crop_cycle_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> dict:
    """Crop-stage-index context plus planting-age-aligned historical observations.

    Age alignment is never represented as a *confirmed* identical growth stage.
    """
    cycle = get_owned_crop_cycle(
        db=db, user_id=current_user.id, crop_cycle_id=crop_cycle_id,
    )
    today = min(_today(), cycle.harvested_on or _today())
    planted = cycle.planted_on
    recorded = list(db.scalars(
        select(CropStageObservation)
        .where(CropStageObservation.crop_cycle_id == crop_cycle_id)
        .order_by(CropStageObservation.observed_on)
    ).all())
    valid_confirmed = [o for o in recorded if o.observed_on <= today]
    # After actual harvest there is no currently growing stage. Retain only
    # historical *farmer-confirmed* stages; never synthesize an active stage.
    stage = valid_confirmed[-1].stage_code if valid_confirmed else (
        None if cycle.harvested_on is not None else provisional_stage(
            crop_name=cycle.crop_name, planted_on=planted, as_of=today,
        )
    )
    source = "farmer_confirmed" if valid_confirmed else (
        "provisional_calendar" if stage else "unknown"
    )
    profile = resolve_profile(cycle.crop_name)
    recommendations = indices_for_stage(stage, profile.key)
    age = (today - planted).days if planted and planted <= today else None
    comparisons: list[dict] = []
    if age is not None:
        other_cycles = list(db.scalars(
            select(CropCycle).where(
                CropCycle.field_id == cycle.field_id,
                CropCycle.id != cycle.id,
            ).order_by(CropCycle.started_on.desc()).limit(30)
        ).all())
        for earlier in other_cycles:
            if resolve_profile(earlier.crop_name).key != profile.key:
                continue
            if not earlier.planted_on or earlier.planted_on >= planted:
                continue
            # No stage claim; compare days-after-planting only with a narrow window.
            target = earlier.planted_on + timedelta(days=age)
            candidate = db.execute(
                select(SatelliteObservation, SatelliteMetric)
                .join(SatelliteMetric,
                      SatelliteMetric.satellite_observation_id == SatelliteObservation.id)
                .where(
                    SatelliteObservation.field_id == cycle.field_id,
                    SatelliteObservation.source == "sentinel-2",
                    SatelliteObservation.observed_on.between(
                        target - timedelta(days=10), target + timedelta(days=10)
                    ),
                    SatelliteMetric.metric_type == "ndvi",
                    SatelliteMetric.valid_pixel_percent >= 80,
                    SatelliteMetric.valid_pixel_count >= 8,
                )
                .order_by(
                    func.abs(SatelliteObservation.observed_on - target),
                    SatelliteMetric.valid_pixel_percent.desc(),
                ).limit(1)
            ).first()
            if candidate:
                observation, metric = candidate
                comparisons.append({
                    "crop_cycle_id": str(earlier.id),
                    "crop": earlier.crop_name,
                    "variety": earlier.variety,
                    "observed_on": observation.observed_on.isoformat(),
                    "days_after_planting": (observation.observed_on-earlier.planted_on).days,
                    "ndvi_median": metric.median,
                    "valid_percent": metric.valid_pixel_percent,
                    "alignment": "planting_age_only",
                })
    return {
        "crop_cycle_id": str(cycle.id),
        "field_id": str(cycle.field_id),
        "crop_name": cycle.crop_name,
        "variety": cycle.variety,
        "profile_key": profile.key,
        "profile_version": profile.version,
        "stage_code": stage,
        "stage_source": source,
        "as_of": today.isoformat(),
        "days_after_planting": age,
        **recommendations,
        "historical_comparisons": comparisons[:10],
        "warnings": [
            *([] if cycle.harvested_on is None else ["Crop has been harvested; any reported farmer stage is a historical observation, not the current stage."]),
            "Unverified crop calendars are not BBCH-confirmed growth stages.",
            "Planting-age matching does not prove equal physiology across seasons/varieties.",
            "Older seasons without comparable optical observations are omitted, not treated as zero.",
        ],
    }
