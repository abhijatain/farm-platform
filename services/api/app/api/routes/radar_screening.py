"""Owner-scoped, read-only radar screening tied to a crop cycle."""
from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DBSession
from app.models.crop_stage_observation import CropStageObservation
from app.models.field import Field
from app.schemas.radar_screening import CropRadarScreeningResponse
from app.services.ownership import get_owned_crop_cycle
from app.services.radar_screening import build_radar_screening
from app.services.satellite_trends import get_field_satellite_trends
from app.services.weather import WeatherProviderError, _today, load_field_weather


router = APIRouter(tags=["radar screening"])


@router.get(
    "/crop-cycles/{crop_cycle_id}/radar-screening",
    response_model=CropRadarScreeningResponse,
)
def get_crop_radar_screening(
    crop_cycle_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    as_of: date | None = Query(default=None),
) -> CropRadarScreeningResponse:
    cycle = get_owned_crop_cycle(
        db=db, user_id=current_user.id, crop_cycle_id=crop_cycle_id,
    )
    reference_start = cycle.planted_on or cycle.started_on
    end = min(_today(), cycle.harvested_on or _today(), as_of or _today())
    if as_of is not None and as_of > _today():
        raise HTTPException(status_code=422, detail="as_of cannot be in the future.")
    if end < reference_start:
        raise HTTPException(status_code=422, detail="as_of cannot precede the crop cycle.")
    start = max(reference_start, end - timedelta(days=180))

    trends = get_field_satellite_trends(
        db=db, field_id=cycle.field_id,
        crop_cycle=cycle, start_date=start, end_date=end,
    )
    observations = list(db.scalars(
        select(CropStageObservation)
        .where(CropStageObservation.crop_cycle_id == cycle.id)
        .order_by(CropStageObservation.observed_on)
    ).all())

    valid_radar_dates = [
        p.observed_on for p in trends.points
        if p.source.startswith("sentinel-1") and p.radar_orbit_key
        and p.metric_type in ("sar_vh_db", "sar_vv_db", "sar_rvi")
        and p.median is not None
        and p.valid_pixel_percent is not None
        and p.valid_pixel_percent >= 80
    ]
    weather_days = []
    weather_warnings = []
    if valid_radar_dates:
        # Only request the three-day windows around each orbit's most recent
        # pass. This is diagnostic context, not an ingestion workflow.
        last_by_orbit = {}
        for point in trends.points:
            if point.observed_on in valid_radar_dates and point.radar_orbit_key:
                last_by_orbit[point.radar_orbit_key] = max(
                    last_by_orbit.get(point.radar_orbit_key, point.observed_on),
                    point.observed_on,
                )
        weather_start = min(last_by_orbit.values()) - timedelta(days=2)
        weather_end = max(last_by_orbit.values())
        row = db.execute(
            select(
                func.ST_Y(func.ST_Centroid(Field.boundary)),
                func.ST_X(func.ST_Centroid(Field.boundary)),
            ).where(Field.id == cycle.field_id)
        ).one()
        try:
            context = load_field_weather(
                field_id=cycle.field_id,
                latitude=float(row[0]),
                longitude=float(row[1]),
                start_date=weather_start,
                end_date=weather_end,
                include_forecast=False,
            )
            weather_days = context.days
            weather_warnings = context.warnings
        except WeatherProviderError:
            weather_warnings = ["Weather context unavailable; radar measurements can still be inspected."]

    return build_radar_screening(
        crop_cycle_id=cycle.id,
        field_id=cycle.field_id,
        crop_name=cycle.crop_name,
        planted_on=cycle.planted_on,
        as_of=end,
        stage_observations=observations,
        trends=trends,
        weather_days=weather_days,
        weather_warnings=weather_warnings,
    )
