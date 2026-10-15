"""Build source-specific field time series without mixing radar orbit geometry."""

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
    "sar_vv_db",
    "sar_vh_db",
    "sar_vv_vh_ratio",
    "sar_rvi",
    "lst_c",
)


def _radar_metadata(
    *,
    source: str,
    metadata_json: dict | None,
) -> tuple[
    str | None,
    int | None,
    str | None,
    str | None,
]:
    if not source.startswith(
        "sentinel-1"
    ):
        return (
            None,
            None,
            None,
            None,
        )

    metadata = (
        metadata_json
        or {}
    )

    orbit_state_raw = (
        metadata.get(
            "orbit_state"
        )
    )

    orbit_state = (
        str(
            orbit_state_raw
        )
        .strip()
        .lower()
        if orbit_state_raw
        is not None
        else None
    )

    relative_orbit_raw = (
        metadata.get(
            "relative_orbit"
        )
    )

    relative_orbit = None

    if (
        relative_orbit_raw
        is not None
    ):
        try:
            relative_orbit = int(
                relative_orbit_raw
            )

        except (
            TypeError,
            ValueError,
        ):
            relative_orbit = None

    platform_raw = (
        metadata.get(
            "platform"
        )
    )

    platform = (
        str(
            platform_raw
        )
        .strip()
        if platform_raw
        is not None
        else None
    )

    radar_orbit_key = None

    if (
        orbit_state
        and relative_orbit
        is not None
    ):
        radar_orbit_key = (
            f"{orbit_state}:"
            f"{relative_orbit}"
        )

    return (
        orbit_state,
        relative_orbit,
        platform,
        radar_orbit_key,
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
            SatelliteObservation
            .metadata_json,
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

    points = []

    for row in rows:
        (
            orbit_state,
            relative_orbit,
            platform,
            radar_orbit_key,
        ) = _radar_metadata(
            source=row[
                2
            ],
            metadata_json=row[
                3
            ],
        )

        points.append(
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
                    4
                ],
                mean=row[
                    5
                ],
                median=row[
                    6
                ],
                valid_pixel_percent=row[
                    7
                ],
                orbit_state=(
                    orbit_state
                ),
                relative_orbit=(
                    relative_orbit
                ),
                platform=platform,
                radar_orbit_key=(
                    radar_orbit_key
                ),
                anomaly_zone_count=int(
                    row[
                        8
                    ]
                    or 0
                ),
                anomaly_area_acres=float(
                    row[
                        9
                    ]
                    or 0.0
                ),
            )
        )

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
