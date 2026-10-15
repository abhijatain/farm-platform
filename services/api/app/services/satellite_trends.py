from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import func, select

from app.api.deps import DBSession
from app.models.activity import Activity
from app.models.crop_cycle import CropCycle
from app.models.satellite_anomaly import SatelliteAnomaly
from app.models.satellite_metric import SatelliteMetric
from app.models.satellite_observation import SatelliteObservation
from app.schemas.satellite_trends import (
    FieldSatelliteTrendsResponse,
    SatelliteTrendActivity,
    SatelliteTrendPoint,
)


TREND_METRIC_TYPES = (
    "ndvi",
    "ndre",
    "ndmi",
    "sar_rvi",
    "lst_c",
)


def _resolve_window(
    *,
    crop_cycle: CropCycle | None,
    start_date: date | None,
    end_date: date | None,
) -> tuple[date, date]:
    resolved_end = (
        end_date
        or (
            crop_cycle.harvested_on
            if (
                crop_cycle is not None
                and crop_cycle.harvested_on is not None
            )
            else date.today()
        )
    )

    resolved_start = (
        start_date
        or (
            (
                crop_cycle.planted_on
                or crop_cycle.started_on
            )
            if crop_cycle is not None
            else (
                resolved_end
                - timedelta(
                    days=365
                )
            )
        )
    )

    if (
        resolved_start
        > resolved_end
    ):
        raise ValueError(
            "start_date cannot be after end_date."
        )

    return (
        resolved_start,
        resolved_end,
    )


def get_field_satellite_trends(
    *,
    db: DBSession,
    field_id: UUID,
    crop_cycle: CropCycle | None,
    start_date: date | None,
    end_date: date | None,
) -> FieldSatelliteTrendsResponse:
    (
        resolved_start,
        resolved_end,
    ) = _resolve_window(
        crop_cycle=crop_cycle,
        start_date=start_date,
        end_date=end_date,
    )

    anomaly_summary = (
        select(
            SatelliteAnomaly
            .satellite_observation_id
            .label(
                "observation_id"
            ),
            SatelliteAnomaly
            .index_type
            .label(
                "metric_type"
            ),
            func.count(
                SatelliteAnomaly.id
            ).label(
                "zone_count"
            ),
            func.coalesce(
                func.sum(
                    SatelliteAnomaly
                    .area_acres
                ),
                0.0,
            ).label(
                "area_acres"
            ),
        )
        .group_by(
            SatelliteAnomaly
            .satellite_observation_id,
            SatelliteAnomaly
            .index_type,
        )
        .subquery()
    )

    rows = db.execute(
        select(
            SatelliteObservation.id,
            SatelliteObservation
            .observed_on,
            SatelliteObservation.source,
            SatelliteMetric
            .metric_type,
            SatelliteMetric.mean,
            SatelliteMetric.median,
            SatelliteMetric
            .valid_pixel_percent,
            func.coalesce(
                anomaly_summary.c
                .zone_count,
                0,
            ),
            func.coalesce(
                anomaly_summary.c
                .area_acres,
                0.0,
            ),
        )
        .join(
            SatelliteMetric,
            SatelliteMetric
            .satellite_observation_id
            == SatelliteObservation.id,
        )
        .outerjoin(
            anomaly_summary,
            (
                anomaly_summary.c
                .observation_id
                == SatelliteObservation.id
            )
            & (
                anomaly_summary.c
                .metric_type
                == SatelliteMetric
                .metric_type
            ),
        )
        .where(
            SatelliteObservation
            .field_id
            == field_id,
            SatelliteObservation
            .observed_on
            >= resolved_start,
            SatelliteObservation
            .observed_on
            <= resolved_end,
            SatelliteMetric
            .metric_type
            .in_(
                TREND_METRIC_TYPES
            ),
        )
        .order_by(
            SatelliteObservation
            .observed_on
            .asc(),
            SatelliteMetric
            .metric_type
            .asc(),
        )
    ).all()

    points = [
        SatelliteTrendPoint(
            observation_id=row[
                0
            ],
            observed_on=row[
                1
            ],
            source=row[
                2
            ],
            metric_type=row[
                3
            ],
            mean=row[
                4
            ],
            median=row[
                5
            ],
            valid_pixel_percent=row[
                6
            ],
            anomaly_zone_count=int(
                row[
                    7
                ]
                or 0
            ),
            anomaly_area_acres=float(
                row[
                    8
                ]
                or 0.0
            ),
        )
        for row in rows
    ]

    activities = db.scalars(
        select(
            Activity
        )
        .where(
            Activity.field_id
            == field_id,
            func.date(
                Activity.occurred_at
            )
            >= resolved_start,
            func.date(
                Activity.occurred_at
            )
            <= resolved_end,
        )
        .order_by(
            Activity
            .occurred_at
            .asc()
        )
    ).all()

    return FieldSatelliteTrendsResponse(
        field_id=field_id,
        crop_cycle_id=(
            crop_cycle.id
            if crop_cycle
            is not None
            else None
        ),
        start_date=(
            resolved_start
        ),
        end_date=(
            resolved_end
        ),
        metric_types=list(
            TREND_METRIC_TYPES
        ),
        points=points,
        activities=[
            SatelliteTrendActivity(
                id=activity.id,
                occurred_at=(
                    activity.occurred_at
                ),
                activity_type=(
                    activity.activity_type
                ),
                notes=(
                    activity.notes
                ),
                crop_cycle_id=(
                    activity.crop_cycle_id
                ),
            )
            for activity
            in activities
        ],
    )
