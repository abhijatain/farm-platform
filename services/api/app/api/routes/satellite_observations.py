
import json
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DBSession, get_current_user, get_db
from app.models.farm import Farm
from app.models.field import Field
from app.models.satellite_anomaly import SatelliteAnomaly
from app.models.satellite_ingestion_job import SatelliteIngestionJob
from app.models.satellite_metric import SatelliteMetric
from app.models.satellite_observation import SatelliteObservation
from app.schemas.satellite_anomaly import (
    SatelliteAnomalyFeature,
    SatelliteAnomalyFeatureCollection,
    SatelliteAnomalyProperties,
)
from app.schemas.satellite_observation import (
    FarmSatelliteOverviewItem,
    SatelliteIngestionJobResponse,
    SatelliteMetricResponse,
    SatelliteObservationResponse,
)
from app.services.ownership import (
    get_owned_farm,
    get_owned_field,
)


router = APIRouter(
    tags=["satellite observations"],
)


@router.get(
    "/farms/{farm_id}/satellite-overview",
    response_model=list[FarmSatelliteOverviewItem],
)
def get_farm_satellite_overview(
    farm_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    metric_type: str = Query(
        default="ndvi",
        min_length=1,
        max_length=32,
    ),
    on_or_before: date | None = Query(
        default=None,
    ),
) -> list[FarmSatelliteOverviewItem]:
    """
    Return the newest available observation for one metric per field.

    When on_or_before is supplied, each field independently resolves to its
    newest observation on or before that date. PostgreSQL DISTINCT ON keeps
    this to one query regardless of the number of fields in the farm.
    """

    get_owned_farm(
        db=db,
        user_id=current_user.id,
        farm_id=farm_id,
    )

    metric_type = (
        metric_type
        .strip()
        .lower()
    )

    statement = (
        select(
            SatelliteObservation,
            SatelliteMetric,
        )
        .join(
            SatelliteMetric,
            SatelliteMetric
            .satellite_observation_id
            == SatelliteObservation.id,
        )
        .join(
            Field,
            Field.id
            == SatelliteObservation.field_id,
        )
        .where(
            Field.farm_id
            == farm_id,
            SatelliteMetric.metric_type
            == metric_type,
        )
    )

    if on_or_before is not None:
        statement = statement.where(
            SatelliteObservation.observed_on
            <= on_or_before
        )

    rows = db.execute(
        statement
        .distinct(
            SatelliteObservation.field_id
        )
        .order_by(
            SatelliteObservation.field_id,
            SatelliteObservation
            .observed_on
            .desc(),
            SatelliteObservation
            .created_at
            .desc(),
        )
    ).all()

    return [
        FarmSatelliteOverviewItem(
            field_id=(
                observation.field_id
            ),
            observation_id=(
                observation.id
            ),
            observed_on=(
                observation.observed_on
            ),
            source=(
                observation.source
            ),
            cloud_cover_percent=(
                observation
                .cloud_cover_percent
            ),
            metric=(
                SatelliteMetricResponse
                .model_validate(
                    metric
                )
            ),
        )
        for (
            observation,
            metric,
        ) in rows
    ]


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
