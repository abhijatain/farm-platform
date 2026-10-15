"""Expose satellite scenes, trends, change and anomaly areas."""

import json
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DBSession, get_current_user, get_db
from app.models.crop_cycle import CropCycle
from app.models.farm import Farm
from app.models.field import Field
from app.models.satellite_anomaly import SatelliteAnomaly
from app.models.satellite_ingestion_job import SatelliteIngestionJob
from app.models.satellite_observation import SatelliteObservation
from app.schemas.satellite_anomaly import (
    SatelliteAnomalyFeature,
    SatelliteAnomalyFeatureCollection,
    SatelliteAnomalyProperties,
)
from app.schemas.satellite_change import (
    FieldSatelliteChangeResponse,
    SatelliteChangeMode,
)
from app.schemas.satellite_observation import (
    SatelliteIngestionJobResponse,
    SatelliteObservationResponse,
)
from app.schemas.satellite_timeline import (
    FieldSatelliteTimelineResponse,
)
from app.schemas.satellite_trends import (
    FieldSatelliteTrendsResponse,
)
from app.services.ownership import (
    get_owned_crop_cycle,
    get_owned_field,
)
from app.services.satellite_change import (
    build_field_satellite_change,
)
from app.services.satellite_timeline import (
    get_field_satellite_timeline,
)
from app.services.satellite_trends import (
    get_field_satellite_trends,
)


router = APIRouter(
    tags=["satellite observations"],
)


@router.get(
    "/fields/{field_id}/satellite-observations",
    response_model=list[SatelliteObservationResponse],
)
def list_satellite_observations(
    field_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> list[SatelliteObservation]:
    get_owned_field(
        db=db,
        user_id=current_user.id,
        field_id=field_id,
    )

    observations = db.scalars(
        select(SatelliteObservation)
        .options(
            selectinload(
                SatelliteObservation.metrics
            )
        )
        .where(
            SatelliteObservation.field_id
            == field_id
        )
        .order_by(
            SatelliteObservation
            .observed_on
            .desc()
        )
    ).all()

    return list(
        observations
    )


@router.get(
    "/fields/{field_id}/satellite-timeline",
    response_model=FieldSatelliteTimelineResponse,
)
def get_satellite_timeline(
    field_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    preferred_metric_type: str = Query(
        default="ndvi",
        min_length=1,
        max_length=32,
    ),
    target_date: date | None = Query(
        default=None,
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
    event_limit: int = Query(
        default=60,
        ge=1,
        le=200,
    ),
) -> FieldSatelliteTimelineResponse:
    get_owned_field(
        db=db,
        user_id=current_user.id,
        field_id=field_id,
    )

    return get_field_satellite_timeline(
        db=db,
        field_id=field_id,
        preferred_metric_type=(
            preferred_metric_type
            .strip()
            .lower()
        ),
        target_date=target_date,
        minimum_valid_percent=(
            minimum_valid_percent
        ),
        window_days=(
            window_days
        ),
        event_limit=(
            event_limit
        ),
    )


@router.get(
    "/fields/{field_id}/satellite-trends",
    response_model=FieldSatelliteTrendsResponse,
)
def get_satellite_trends(
    field_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    crop_cycle_id: UUID | None = Query(
        default=None,
    ),
    start_date: date | None = Query(
        default=None,
    ),
    end_date: date | None = Query(
        default=None,
    ),
) -> FieldSatelliteTrendsResponse:
    get_owned_field(
        db=db,
        user_id=current_user.id,
        field_id=field_id,
    )

    crop_cycle = None

    if crop_cycle_id is not None:
        crop_cycle = get_owned_crop_cycle(
            db=db,
            user_id=current_user.id,
            crop_cycle_id=crop_cycle_id,
        )

        if (
            crop_cycle.field_id
            != field_id
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
                detail=(
                    "Crop cycle does not belong to this field."
                ),
            )

    try:
        return get_field_satellite_trends(
            db=db,
            field_id=field_id,
            crop_cycle=crop_cycle,
            start_date=start_date,
            end_date=end_date,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(
                error
            ),
        ) from error


@router.get(
    "/fields/{field_id}/satellite-change",
    response_model=FieldSatelliteChangeResponse,
)
def get_satellite_change(
    field_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    metric_type: str = Query(
        default="ndvi",
        min_length=1,
        max_length=32,
    ),
    mode: SatelliteChangeMode = Query(
        default="previous",
    ),
    to_date: date | None = Query(
        default=None,
    ),
    from_date: date | None = Query(
        default=None,
    ),
    crop_cycle_id: UUID | None = Query(
        default=None,
    ),
    minimum_valid_percent: float = Query(
        default=80.0,
        ge=0.0,
        le=100.0,
    ),
    date_tolerance_days: int = Query(
        default=7,
        ge=0,
        le=30,
    ),
    pixel_change_threshold: float | None = Query(
        default=None,
        ge=0.0,
    ),
) -> FieldSatelliteChangeResponse:
    get_owned_field(
        db=db,
        user_id=current_user.id,
        field_id=field_id,
    )

    normalized_metric_type = (
        metric_type
        .strip()
        .lower()
    )

    if (
        mode == "custom"
        and from_date is None
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "from_date is required for custom comparison."
            ),
        )

    resolved_crop_cycle = None

    if mode == "crop_start":
        if crop_cycle_id is not None:
            resolved_crop_cycle = (
                get_owned_crop_cycle(
                    db=db,
                    user_id=current_user.id,
                    crop_cycle_id=crop_cycle_id,
                )
            )

            if (
                resolved_crop_cycle.field_id
                != field_id
            ):
                raise HTTPException(
                    status_code=(
                        status.HTTP_422_UNPROCESSABLE_ENTITY
                    ),
                    detail=(
                        "Crop cycle does not belong to this field."
                    ),
                )

        else:
            resolved_crop_cycle = db.scalar(
                select(
                    CropCycle
                )
                .where(
                    CropCycle.field_id
                    == field_id
                )
                .order_by(
                    case(
                        (
                            CropCycle.status
                            == "active",
                            0,
                        ),
                        else_=1,
                    ),
                    CropCycle.started_on.desc(),
                )
                .limit(
                    1
                )
            )

        if resolved_crop_cycle is None:
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
                detail=(
                    "No crop cycle is available for crop-start comparison."
                ),
            )

    return build_field_satellite_change(
        db=db,
        field_id=field_id,
        metric_type=(
            normalized_metric_type
        ),
        mode=mode,
        requested_to_date=(
            to_date
        ),
        requested_from_date=(
            from_date
        ),
        crop_cycle_id=(
            resolved_crop_cycle.id
            if resolved_crop_cycle
            is not None
            else None
        ),
        crop_reference_date=(
            (
                resolved_crop_cycle.planted_on
                or resolved_crop_cycle.started_on
            )
            if resolved_crop_cycle
            is not None
            else None
        ),
        minimum_valid_percent=(
            minimum_valid_percent
        ),
        date_tolerance_days=(
            date_tolerance_days
        ),
        pixel_change_threshold=(
            pixel_change_threshold
        ),
    )


@router.get(
    "/fields/{field_id}/satellite-ingestion",
    response_model=SatelliteIngestionJobResponse | None,
)
def get_satellite_ingestion_status(
    field_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> SatelliteIngestionJob | None:
    get_owned_field(
        db=db,
        user_id=current_user.id,
        field_id=field_id,
    )

    return db.scalar(
        select(
            SatelliteIngestionJob
        )
        .where(
            SatelliteIngestionJob.field_id
            == field_id
        )
        .order_by(
            case(
                (
                    SatelliteIngestionJob.status
                    == "running",
                    0,
                ),
                (
                    SatelliteIngestionJob.status
                    == "pending",
                    1,
                ),
                (
                    SatelliteIngestionJob.status
                    == "failed",
                    2,
                ),
                else_=3,
            ),
            case(
                (
                    SatelliteIngestionJob.job_type
                    == "initial_backfill",
                    0,
                ),
                else_=1,
            ),
            SatelliteIngestionJob
            .created_at
            .desc(),
        )
        .limit(1)
    )


@router.get(
    "/satellite-observations/{observation_id}/anomalies",
    response_model=SatelliteAnomalyFeatureCollection,
)
def list_satellite_anomalies(
    observation_id: UUID,
    metric_type: str = Query(
        default="ndvi",
        min_length=1,
        max_length=20,
    ),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    metric_type = (
        metric_type
        .strip()
        .lower()
    )

    observation = db.scalar(
        select(SatelliteObservation)
        .join(
            Field,
            Field.id
            == SatelliteObservation.field_id,
        )
        .join(
            Farm,
            Farm.id
            == Field.farm_id,
        )
        .where(
            SatelliteObservation.id
            == observation_id,
            Farm.owner_user_id
            == current_user.id,
        )
    )

    if observation is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Satellite observation "
                "not found."
            ),
        )

    rows = db.execute(
        select(
            SatelliteAnomaly,
            func.ST_AsGeoJSON(
                SatelliteAnomaly.geometry
            ).label(
                "geometry_geojson"
            ),
        )
        .where(
            SatelliteAnomaly
            .satellite_observation_id
            == observation_id,
            SatelliteAnomaly.index_type
            == metric_type,
        )
        .order_by(
            SatelliteAnomaly.zone_index
        )
    ).all()

    features = []

    for (
        anomaly,
        geometry_geojson,
    ) in rows:
        features.append(
            SatelliteAnomalyFeature(
                id=anomaly.id,
                geometry=json.loads(
                    geometry_geojson
                ),
                properties=(
                    SatelliteAnomalyProperties(
                        id=anomaly.id,
                        satellite_observation_id=(
                            anomaly
                            .satellite_observation_id
                        ),
                        # field_id is derived from the owned observation.
                        # It is no longer redundantly stored on each anomaly.
                        field_id=(
                            observation.field_id
                        ),
                        zone_index=(
                            anomaly.zone_index
                        ),
                        index_type=(
                            anomaly.index_type
                        ),
                        anomaly_type=(
                            anomaly.anomaly_type
                        ),
                        severity=(
                            anomaly.severity
                        ),
                        pixel_count=(
                            anomaly.pixel_count
                        ),
                        area_sqm=(
                            anomaly.area_sqm
                        ),
                        area_acres=(
                            anomaly.area_acres
                        ),
                        zone_mean_value=(
                            anomaly
                            .zone_mean_value
                        ),
                        zone_min_value=(
                            anomaly
                            .zone_min_value
                        ),
                        zone_max_value=(
                            anomaly
                            .zone_max_value
                        ),
                        field_mean_value=(
                            anomaly
                            .field_mean_value
                        ),
                        field_median_value=(
                            anomaly
                            .field_median_value
                        ),
                        threshold_value=(
                            anomaly
                            .threshold_value
                        ),
                        difference_from_field=(
                            anomaly
                            .difference_from_field
                        ),
                        percent_difference=(
                            anomaly
                            .percent_difference
                        ),
                        detection_method=(
                            anomaly
                            .detection_method
                        ),
                    )
                ),
            )
        )

    return SatelliteAnomalyFeatureCollection(
        features=features,
    )
