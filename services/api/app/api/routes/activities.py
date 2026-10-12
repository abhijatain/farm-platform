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


PERCENT_CHANGE_MINIMUM_BASELINE_ABS = 0.05
SQUARE_METRES_PER_ACRE = 4046.8564224
SPATIAL_PERSISTENCE_BASIS = "same_anomaly_type_overlap"


def _find_nearest_metric_observation(
    *,
    db: DBSession,
    field_id: UUID,
    activity_date: date,
    metric_type: str,
    window_days: int,
    minimum_valid_percent: float,
    direction: Literal["before", "after"],
) -> tuple[SatelliteObservation, SatelliteMetric] | None:
    if direction == "before":
        lower_date = activity_date - timedelta(days=window_days)

        date_filters = (
            SatelliteObservation.observed_on < activity_date,
            SatelliteObservation.observed_on >= lower_date,
        )

        ordering = (
            SatelliteObservation.observed_on.desc(),
            SatelliteMetric.valid_pixel_percent.desc(),
        )

    else:
        upper_date = activity_date + timedelta(days=window_days)

        date_filters = (
            SatelliteObservation.observed_on > activity_date,
            SatelliteObservation.observed_on <= upper_date,
        )

        ordering = (
            SatelliteObservation.observed_on.asc(),
            SatelliteMetric.valid_pixel_percent.desc(),
        )

    row = db.execute(
        select(
            SatelliteObservation,
            SatelliteMetric,
        )
        .join(
            SatelliteMetric,
            SatelliteMetric.satellite_observation_id == SatelliteObservation.id,
        )
        .where(
            SatelliteObservation.field_id == field_id,
            SatelliteMetric.metric_type == metric_type,
            SatelliteMetric.valid_pixel_percent >= minimum_valid_percent,
            SatelliteMetric.raster_uri.is_not(None),
            *date_filters,
        )
        .order_by(*ordering)
        .limit(1)
    ).first()

    if row is None:
        return None

    observation, metric = row

    return observation, metric


def _get_anomaly_summary(
    *,
    db: DBSession,
    observation_id: UUID,
    metric_type: str,
) -> tuple[int, float, float]:
    row = db.execute(
        select(
            func.count(SatelliteAnomaly.id),
            func.coalesce(
                func.sum(SatelliteAnomaly.area_sqm),
                0.0,
            ),
            func.coalesce(
                func.sum(SatelliteAnomaly.area_acres),
                0.0,
            ),
        ).where(
            SatelliteAnomaly.satellite_observation_id == observation_id,
            SatelliteAnomaly.index_type == metric_type,
        )
    ).one()

    return (
        int(row[0]),
        float(row[1]),
        float(row[2]),
    )


def _build_satellite_match(
    *,
    db: DBSession,
    activity_date: date,
    metric_type: str,
    observation: SatelliteObservation,
    metric: SatelliteMetric,
) -> ActivitySatelliteObservationMatch:
    (
        anomaly_zone_count,
        anomaly_area_sqm,
        anomaly_area_acres,
    ) = _get_anomaly_summary(
        db=db,
        observation_id=observation.id,
        metric_type=metric_type,
    )

    return ActivitySatelliteObservationMatch(
        observation_id=observation.id,
        observed_on=observation.observed_on,
        days_from_activity=(observation.observed_on - activity_date).days,
        source=observation.source,
        scene_id=observation.scene_id,
        metric_type=metric_type,
        valid_pixel_percent=float(metric.valid_pixel_percent),
        mean=metric.mean,
        median=metric.median,
        minimum=metric.min,
        maximum=metric.max,
        std=metric.std,
        raster_uri=metric.raster_uri,
        native_resolution_m=(metric.native_resolution_m),
        output_resolution_m=(metric.output_resolution_m),
        anomaly_zone_count=(anomaly_zone_count),
        anomaly_area_sqm=(anomaly_area_sqm),
        anomaly_area_acres=(anomaly_area_acres),
    )


def _absolute_change(
    before: float | None,
    after: float | None,
) -> float | None:
    if before is None or after is None:
        return None

    return float(after - before)


def _percent_change(
    before: float | None,
    after: float | None,
) -> float | None:
    if before is None or after is None:
        return None

    if abs(before) < PERCENT_CHANGE_MINIMUM_BASELINE_ABS:
        return None

    return float(((after - before) / abs(before)) * 100.0)


def _comparison_status(
    *,
    before: ActivitySatelliteObservationMatch | None,
    after: ActivitySatelliteObservationMatch | None,
) -> Literal[
    "complete",
    "missing_before",
    "missing_after",
    "missing_both",
]:
    if before is None and after is None:
        return "missing_both"

    if before is None:
        return "missing_before"

    if after is None:
        return "missing_after"

    return "complete"


def _build_comparison(
    *,
    before: ActivitySatelliteObservationMatch | None,
    after: ActivitySatelliteObservationMatch | None,
) -> ActivitySatelliteComparison:
    status_value = _comparison_status(
        before=before,
        after=after,
    )

    if before is None or after is None:
        return ActivitySatelliteComparison(
            status=status_value,
            mean_change=None,
            mean_percent_change=None,
            median_change=None,
            median_percent_change=None,
            anomaly_zone_count_change=None,
            anomaly_area_sqm_change=None,
            anomaly_area_acres_change=None,
            percent_change_minimum_baseline_abs=(PERCENT_CHANGE_MINIMUM_BASELINE_ABS),
        )

    return ActivitySatelliteComparison(
        status="complete",
        mean_change=_absolute_change(
            before.mean,
            after.mean,
        ),
        mean_percent_change=_percent_change(
            before.mean,
            after.mean,
        ),
        median_change=_absolute_change(
            before.median,
            after.median,
        ),
        median_percent_change=_percent_change(
            before.median,
            after.median,
        ),
        anomaly_zone_count_change=(
            after.anomaly_zone_count - before.anomaly_zone_count
        ),
        anomaly_area_sqm_change=(after.anomaly_area_sqm - before.anomaly_area_sqm),
        anomaly_area_acres_change=(
            after.anomaly_area_acres - before.anomaly_area_acres
        ),
        percent_change_minimum_baseline_abs=(PERCENT_CHANGE_MINIMUM_BASELINE_ABS),
    )


def _sqm_to_acres(
    area_sqm: float,
) -> float:
    return float(area_sqm / SQUARE_METRES_PER_ACRE)


def _decode_geojson(
    value: str | None,
) -> dict | None:
    if value is None:
        return None

    return json.loads(value)


def _build_spatial_comparison(
    *,
    db: DBSession,
    metric_type: str,
    before: ActivitySatelliteObservationMatch | None,
    after: ActivitySatelliteObservationMatch | None,
) -> ActivitySatelliteSpatialComparison:
    status_value = _comparison_status(
        before=before,
        after=after,
    )

    if before is None or after is None:
        return ActivitySatelliteSpatialComparison(
            status=status_value,
            persistence_basis=(SPATIAL_PERSISTENCE_BASIS),
            before_anomaly_area_sqm=(
                before.anomaly_area_sqm if before is not None else None
            ),
            before_anomaly_area_acres=(
                before.anomaly_area_acres if before is not None else None
            ),
            after_anomaly_area_sqm=(
                after.anomaly_area_sqm if after is not None else None
            ),
            after_anomaly_area_acres=(
                after.anomaly_area_acres if after is not None else None
            ),
            persistent_area_sqm=None,
            persistent_area_acres=None,
            resolved_area_sqm=None,
            resolved_area_acres=None,
            new_area_sqm=None,
            new_area_acres=None,
            persistent_geometry=None,
            resolved_geometry=None,
            new_geometry=None,
        )

    statement = text(
        """
        WITH before_by_type AS (
            SELECT
                anomaly_type,
                ST_UnaryUnion(
                    ST_Collect(
                        ST_MakeValid(geometry)
                    )
                ) AS geom

            FROM satellite_anomalies

            WHERE
                satellite_observation_id
                    = :before_observation_id
                AND index_type
                    = :metric_type

            GROUP BY
                anomaly_type
        ),

        after_by_type AS (
            SELECT
                anomaly_type,
                ST_UnaryUnion(
                    ST_Collect(
                        ST_MakeValid(geometry)
                    )
                ) AS geom

            FROM satellite_anomalies

            WHERE
                satellite_observation_id
                    = :after_observation_id
                AND index_type
                    = :metric_type

            GROUP BY
                anomaly_type
        ),

        before_union AS (
            SELECT
                ST_UnaryUnion(
                    ST_Collect(geom)
                ) AS geom

            FROM before_by_type
        ),

        after_union AS (
            SELECT
                ST_UnaryUnion(
                    ST_Collect(geom)
                ) AS geom

            FROM after_by_type
        ),

        persistent_parts AS (
            SELECT
                ST_Intersection(
                    before_by_type.geom,
                    after_by_type.geom
                ) AS geom

            FROM before_by_type

            JOIN after_by_type
                ON after_by_type.anomaly_type
                    = before_by_type.anomaly_type
        ),

        persistent_union AS (
            SELECT
                ST_UnaryUnion(
                    ST_Collect(geom)
                ) AS geom

            FROM persistent_parts
        ),

        normalized AS (
            SELECT
                ST_Multi(
                    ST_CollectionExtract(
                        ST_MakeValid(
                            COALESCE(
                                before_union.geom,
                                ST_GeomFromText(
                                    'MULTIPOLYGON EMPTY',
                                    4326
                                )
                            )
                        ),
                        3
                    )
                ) AS before_geom,

                ST_Multi(
                    ST_CollectionExtract(
                        ST_MakeValid(
                            COALESCE(
                                after_union.geom,
                                ST_GeomFromText(
                                    'MULTIPOLYGON EMPTY',
                                    4326
                                )
                            )
                        ),
                        3
                    )
                ) AS after_geom,

                ST_Multi(
                    ST_CollectionExtract(
                        ST_MakeValid(
                            COALESCE(
                                persistent_union.geom,
                                ST_GeomFromText(
                                    'MULTIPOLYGON EMPTY',
                                    4326
                                )
                            )
                        ),
                        3
                    )
                ) AS persistent_geom

            FROM
                before_union,
                after_union,
                persistent_union
        ),

        parts AS (
            SELECT
                before_geom,
                after_geom,
                persistent_geom,

                ST_Multi(
                    ST_CollectionExtract(
                        ST_MakeValid(
                            ST_Difference(
                                before_geom,
                                persistent_geom
                            )
                        ),
                        3
                    )
                ) AS resolved_geom,

                ST_Multi(
                    ST_CollectionExtract(
                        ST_MakeValid(
                            ST_Difference(
                                after_geom,
                                persistent_geom
                            )
                        ),
                        3
                    )
                ) AS new_geom

            FROM normalized
        )

        SELECT
            ST_Area(
                before_geom::geography
            ) AS before_area_sqm,

            ST_Area(
                after_geom::geography
            ) AS after_area_sqm,

            ST_Area(
                persistent_geom::geography
            ) AS persistent_area_sqm,

            ST_Area(
                resolved_geom::geography
            ) AS resolved_area_sqm,

            ST_Area(
                new_geom::geography
            ) AS new_area_sqm,

            CASE
                WHEN ST_IsEmpty(
                    persistent_geom
                )
                THEN NULL
                ELSE ST_AsGeoJSON(
                    persistent_geom
                )
            END AS persistent_geojson,

            CASE
                WHEN ST_IsEmpty(
                    resolved_geom
                )
                THEN NULL
                ELSE ST_AsGeoJSON(
                    resolved_geom
                )
            END AS resolved_geojson,

            CASE
                WHEN ST_IsEmpty(
                    new_geom
                )
                THEN NULL
                ELSE ST_AsGeoJSON(
                    new_geom
                )
            END AS new_geojson

        FROM parts
        """
    )

    row = (
        db.execute(
            statement,
            {
                "before_observation_id": (before.observation_id),
                "after_observation_id": (after.observation_id),
                "metric_type": metric_type,
            },
        )
        .mappings()
        .one()
    )

    before_area_sqm = float(row["before_area_sqm"] or 0.0)

    after_area_sqm = float(row["after_area_sqm"] or 0.0)

    persistent_area_sqm = float(row["persistent_area_sqm"] or 0.0)

    resolved_area_sqm = float(row["resolved_area_sqm"] or 0.0)

    new_area_sqm = float(row["new_area_sqm"] or 0.0)

    return ActivitySatelliteSpatialComparison(
        status="complete",
        persistence_basis=(SPATIAL_PERSISTENCE_BASIS),
        before_anomaly_area_sqm=(before_area_sqm),
        before_anomaly_area_acres=(_sqm_to_acres(before_area_sqm)),
        after_anomaly_area_sqm=(after_area_sqm),
        after_anomaly_area_acres=(_sqm_to_acres(after_area_sqm)),
        persistent_area_sqm=(persistent_area_sqm),
        persistent_area_acres=(_sqm_to_acres(persistent_area_sqm)),
        resolved_area_sqm=(resolved_area_sqm),
        resolved_area_acres=(_sqm_to_acres(resolved_area_sqm)),
        new_area_sqm=(new_area_sqm),
        new_area_acres=(_sqm_to_acres(new_area_sqm)),
        persistent_geometry=(_decode_geojson(row["persistent_geojson"])),
        resolved_geometry=(_decode_geojson(row["resolved_geojson"])),
        new_geometry=(_decode_geojson(row["new_geojson"])),
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
