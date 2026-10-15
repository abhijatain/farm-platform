"""Accept farmer activities and expose activity-linked satellite evidence."""

import json
from datetime import date, timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select, text

from app.api.deps import CurrentUser, DBSession
from app.models.activity import Activity
from app.models.crop_cycle import CropCycle
from app.models.satellite_anomaly import SatelliteAnomaly
from app.models.satellite_metric import SatelliteMetric
from app.models.satellite_observation import SatelliteObservation
from app.models.season import Season
from app.schemas.activity import ActivityCreate, ActivityResponse
from app.schemas.activity_satellite import (
    ActivitySatelliteComparison,
    ActivitySatelliteContextResponse,
    ActivitySatelliteObservationMatch,
    ActivitySatelliteSpatialComparison,
)
from app.schemas.timeline import TimelineItem
from app.services.ownership import get_owned_crop_cycle, get_owned_field

router = APIRouter(
    tags=["activities"],
)


# Extracted metric selection and geospatial comparisons are reusable services.
from app.services.activity_satellite import (
    _find_nearest_metric_observation,
    _get_anomaly_summary,
    _build_satellite_match,
    _absolute_change,
    _percent_change,
    _comparison_status,
    _build_comparison,
    _sqm_to_acres,
    _decode_geojson,
    _build_spatial_comparison,
)


@router.post(
    "/fields/{field_id}/activities",
    response_model=ActivityResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_activity(
    field_id: UUID,
    data: ActivityCreate,
    db: DBSession,
    current_user: CurrentUser,
) -> Activity:
    field = get_owned_field(
        db=db,
        user_id=current_user.id,
        field_id=field_id,
    )

    crop_cycle = None

    if data.crop_cycle_id is not None:
        crop_cycle = get_owned_crop_cycle(
            db=db,
            user_id=current_user.id,
            crop_cycle_id=data.crop_cycle_id,
        )

        if crop_cycle.field_id != field.id:
            raise HTTPException(
                status_code=(status.HTTP_422_UNPROCESSABLE_ENTITY),
                detail=("The selected crop cycle does not " "belong to this field."),
            )

    activity = Activity(
        field_id=field.id,
        crop_cycle_id=(crop_cycle.id if crop_cycle is not None else None),
        activity_type=data.activity_type,
        occurred_at=data.occurred_at,
        notes=data.notes,
        details=data.details,
    )

    db.add(activity)
    db.commit()
    db.refresh(activity)

    return activity


@router.get(
    "/fields/{field_id}/activities",
    response_model=list[ActivityResponse],
)
def list_field_activities(
    field_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> list[Activity]:
    get_owned_field(
        db=db,
        user_id=current_user.id,
        field_id=field_id,
    )

    activities = db.scalars(
        select(Activity)
        .where(Activity.field_id == field_id)
        .order_by(Activity.occurred_at.desc())
    ).all()

    return list(activities)


@router.get(
    "/activities/{activity_id}/satellite-context",
    response_model=ActivitySatelliteContextResponse,
)
def get_activity_satellite_context(
    activity_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    metric_type: str = Query(
        default="ndvi",
        min_length=1,
        max_length=32,
    ),
    window_days: int = Query(
        default=14,
        ge=1,
        le=60,
    ),
    minimum_valid_percent: float = Query(
        default=80.0,
        ge=0.0,
        le=100.0,
    ),
) -> ActivitySatelliteContextResponse:
    activity = db.scalar(select(Activity).where(Activity.id == activity_id))

    if activity is None:
        raise HTTPException(
            status_code=(status.HTTP_404_NOT_FOUND),
            detail="Activity not found.",
        )

    get_owned_field(
        db=db,
        user_id=current_user.id,
        field_id=activity.field_id,
    )

    normalized_metric_type = metric_type.strip().lower()

    if not normalized_metric_type:
        raise HTTPException(
            status_code=(status.HTTP_422_UNPROCESSABLE_ENTITY),
            detail=("metric_type cannot be empty."),
        )

    activity_date = activity.occurred_at.date()

    before_row = _find_nearest_metric_observation(
        db=db,
        field_id=activity.field_id,
        activity_date=activity_date,
        metric_type=(normalized_metric_type),
        window_days=window_days,
        minimum_valid_percent=(minimum_valid_percent),
        direction="before",
    )

    after_row = _find_nearest_metric_observation(
        db=db,
        field_id=activity.field_id,
        activity_date=activity_date,
        metric_type=(normalized_metric_type),
        window_days=window_days,
        minimum_valid_percent=(minimum_valid_percent),
        direction="after",
    )

    before = (
        _build_satellite_match(
            db=db,
            activity_date=activity_date,
            metric_type=(normalized_metric_type),
            observation=before_row[0],
            metric=before_row[1],
        )
        if before_row is not None
        else None
    )

    after = (
        _build_satellite_match(
            db=db,
            activity_date=activity_date,
            metric_type=(normalized_metric_type),
            observation=after_row[0],
            metric=after_row[1],
        )
        if after_row is not None
        else None
    )

    comparison = _build_comparison(
        before=before,
        after=after,
    )

    spatial_comparison = _build_spatial_comparison(
        db=db,
        metric_type=(normalized_metric_type),
        before=before,
        after=after,
    )

    return ActivitySatelliteContextResponse(
        activity_id=activity.id,
        field_id=activity.field_id,
        activity_type=(activity.activity_type),
        occurred_at=(activity.occurred_at),
        metric_type=(normalized_metric_type),
        search_window_days=(window_days),
        minimum_valid_percent=(minimum_valid_percent),
        before=before,
        after=after,
        comparison=comparison,
        spatial_comparison=(spatial_comparison),
    )


@router.get(
    "/fields/{field_id}/timeline",
    response_model=list[TimelineItem],
)
def get_field_timeline(
    field_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> list[TimelineItem]:
    get_owned_field(
        db=db,
        user_id=current_user.id,
        field_id=field_id,
    )

    statement = (
        select(
            Activity,
            CropCycle,
            Season,
        )
        .outerjoin(
            CropCycle,
            CropCycle.id == Activity.crop_cycle_id,
        )
        .outerjoin(
            Season,
            Season.id == CropCycle.season_id,
        )
        .where(Activity.field_id == field_id)
        .order_by(Activity.occurred_at.desc())
    )

    rows = db.execute(statement).all()

    timeline: list[TimelineItem] = []

    for activity, crop_cycle, season in rows:
        timeline.append(
            TimelineItem(
                id=activity.id,
                occurred_at=(activity.occurred_at),
                activity_type=(activity.activity_type),
                notes=activity.notes,
                details=activity.details,
                crop_cycle_id=(crop_cycle.id if crop_cycle else None),
                crop_name=(crop_cycle.crop_name if crop_cycle else None),
                variety=(crop_cycle.variety if crop_cycle else None),
                season_id=(season.id if season else None),
                season_name=(season.name if season else None),
            )
        )

    return timeline
