from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession
from app.models.satellite_metric import (
    SatelliteMetric,
)
from app.models.satellite_observation import (
    SatelliteObservation,
)
from app.schemas.satellite_timeline import (
    FieldSatelliteTimelineResponse,
    SatelliteTimelineEvent,
    SatelliteTimelineMetricSummary,
    SatelliteTimelineSelection,
    SatelliteTimelineSelectionMatch,
)


RADAR_FALLBACK_METRIC_TYPES = (
    "sar_rvi",
    "sar_vh_db",
    "sar_vv_db",
    "sar_vv_vh_ratio",
)


def source_kind(
    source: str,
) -> str:
    normalized = (
        source
        .strip()
        .lower()
    )

    if normalized.startswith(
        "sentinel-1"
    ):
        return "radar"

    if normalized.startswith(
        "sentinel-2"
    ):
        return "optical"

    if normalized.startswith(
        "landsat"
    ):
        return "thermal"

    return "other"


def timeline_status(
    observation: SatelliteObservation,
) -> str:
    processing_status = (
        observation
        .metadata_json
        .get(
            "processing_status"
        )
        if observation
        .metadata_json
        else None
    )

    if (
        processing_status
        == "skipped_scene_cloud_cover"
    ):
        return "cloud_skipped"

    if (
        processing_status
        == "skipped_no_usable_pixels"
    ):
        return "unusable"

    if (
        isinstance(
            processing_status,
            str,
        )
        and processing_status
        .startswith(
            "skipped_"
        )
    ):
        return "skipped"

    if observation.metrics:
        return "usable"

    return "unavailable"


def representative_metric(
    observation: SatelliteObservation,
) -> SatelliteMetric | None:
    kind = source_kind(
        observation.source
    )

    preferred = {
        "optical":
            (
                "ndvi",
                "ndmi",
                "ndre",
            ),
        "radar":
            RADAR_FALLBACK_METRIC_TYPES,
        "thermal":
            (
                "lst_c",
            ),
    }.get(
        kind,
        (),
    )

    by_type = {
        metric.metric_type:
            metric
        for metric
        in observation.metrics
    }

    for metric_type in preferred:
        metric = by_type.get(
            metric_type
        )

        if metric is not None:
            return metric

    return (
        observation.metrics[
            0
        ]
        if observation.metrics
        else None
    )


def _metric_summary(
    metric: SatelliteMetric
    | None,
) -> SatelliteTimelineMetricSummary | None:
    if metric is None:
        return None

    return SatelliteTimelineMetricSummary(
        metric_type=(
            metric.metric_type
        ),
        mean=metric.mean,
        median=metric.median,
        valid_pixel_percent=(
            metric.valid_pixel_percent
        ),
        raster_uri=(
            metric.raster_uri
        ),
    )


def _event_from_observation(
    observation: SatelliteObservation,
) -> SatelliteTimelineEvent:
    metadata = (
        observation
        .metadata_json
        or {}
    )

    field_cloud = (
        metadata.get(
            "field_cloud_cover_percent"
        )
    )

    if not isinstance(
        field_cloud,
        (
            int,
            float,
        ),
    ):
        field_cloud = None

    kind = source_kind(
        observation.source
    )

    return SatelliteTimelineEvent(
        observation_id=(
            observation.id
        ),
        observed_on=(
            observation.observed_on
        ),
        source=(
            observation.source
        ),
        source_kind=kind,
        scene_id=(
            observation.scene_id
        ),
        status=(
            timeline_status(
                observation
            )
        ),
        processing_status=(
            metadata.get(
                "processing_status"
            )
        ),
        cloud_cover_percent=(
            observation
            .cloud_cover_percent
        ),
        field_cloud_cover_percent=(
            float(
                field_cloud
            )
            if field_cloud
            is not None
            else None
        ),
        cloud_independent=(
            kind
            == "radar"
        ),
        metric_types=sorted(
            metric.metric_type
            for metric
            in observation.metrics
        ),
        representative_metric=(
            _metric_summary(
                representative_metric(
                    observation
                )
            )
        ),
    )


def _nearest_metric_match(
    *,
    observations: Iterable[
        SatelliteObservation
    ],
    target_date: date,
    metric_types: tuple[
        str,
        ...,
    ],
    minimum_valid_percent: float,
    window_days: int,
) -> SatelliteTimelineSelectionMatch | None:
    priority = {
        metric_type:
            index
        for (
            index,
            metric_type,
        )
        in enumerate(
            metric_types
        )
    }

    candidates: list[
        tuple[
            int,
            int,
            int,
            float,
            SatelliteObservation,
            SatelliteMetric,
        ]
    ] = []

    for observation in observations:
        days_from_target = (
            observation.observed_on
            - target_date
        ).days

        if (
            abs(
                days_from_target
            )
            > window_days
        ):
            continue

        for metric in observation.metrics:
            if (
                metric.metric_type
                not in priority
            ):
                continue

            valid_percent = (
                metric
                .valid_pixel_percent
            )

            if (
                valid_percent
                is not None
                and valid_percent
                < minimum_valid_percent
            ):
                continue

            candidates.append(
                (
                    abs(
                        days_from_target
                    ),
                    0
                    if days_from_target
                    <= 0
                    else 1,
                    priority[
                        metric.metric_type
                    ],
                    -float(
                        valid_percent
                        or 0.0
                    ),
                    observation,
                    metric,
                )
            )

    if not candidates:
        return None

    (
        _,
        _,
        _,
        _,
        observation,
        metric,
    ) = min(
        candidates,
        key=lambda item: (
            item[
                0
            ],
            item[
                1
            ],
            item[
                2
            ],
            item[
                3
            ],
            -item[
                4
            ].observed_on.toordinal(),
        ),
    )

    return SatelliteTimelineSelectionMatch(
        observation_id=(
            observation.id
        ),
        observed_on=(
            observation.observed_on
        ),
        days_from_target=(
            observation.observed_on
            - target_date
        ).days,
        source=(
            observation.source
        ),
        source_kind=(
            source_kind(
                observation.source
            )
        ),
        metric_type=(
            metric.metric_type
        ),
        median=(
            metric.median
        ),
        mean=(
            metric.mean
        ),
        valid_pixel_percent=(
            metric.valid_pixel_percent
        ),
        raster_uri=(
            metric.raster_uri
        ),
    )


def _optical_unavailable_on_target(
    *,
    observations: Iterable[
        SatelliteObservation
    ],
    target_date: date,
) -> bool:
    return any(
        observation.observed_on
        == target_date
        and source_kind(
            observation.source
        )
        == "optical"
        and timeline_status(
            observation
        )
        in {
            "cloud_skipped",
            "unusable",
            "skipped",
            "unavailable",
        }
        for observation
        in observations
    )


def build_satellite_timeline(
    *,
    field_id: UUID,
    observations: list[
        SatelliteObservation
    ],
    preferred_metric_type: str,
    target_date: date | None,
    minimum_valid_percent: float,
    window_days: int,
) -> FieldSatelliteTimelineResponse:
    sorted_observations = sorted(
        observations,
        key=lambda item: (
            item.observed_on,
            item.created_at,
        ),
        reverse=True,
    )

    resolved_target_date = (
        target_date
        or (
            sorted_observations[
                0
            ].observed_on
            if sorted_observations
            else date.today()
        )
    )

    preferred = (
        _nearest_metric_match(
            observations=(
                sorted_observations
            ),
            target_date=(
                resolved_target_date
            ),
            metric_types=(
                preferred_metric_type,
            ),
            minimum_valid_percent=(
                minimum_valid_percent
            ),
            window_days=(
                window_days
            ),
        )
    )

    radar = (
        _nearest_metric_match(
            observations=(
                sorted_observations
            ),
            target_date=(
                resolved_target_date
            ),
            metric_types=(
                RADAR_FALLBACK_METRIC_TYPES
            ),
            minimum_valid_percent=(
                minimum_valid_percent
            ),
            window_days=(
                window_days
            ),
        )
    )

    optical_unavailable = (
        _optical_unavailable_on_target(
            observations=(
                sorted_observations
            ),
            target_date=(
                resolved_target_date
            ),
        )
    )

    recommended_kind = (
        "none"
    )

    recommended = None

    reason = None

    if (
        optical_unavailable
        and radar is not None
        and (
            preferred is None
            or abs(
                radar.days_from_target
            )
            < abs(
                preferred.days_from_target
            )
        )
    ):
        recommended_kind = (
            "radar_fallback"
        )

        recommended = radar

        reason = (
            "Optical imagery is unavailable on the target date. "
            "The nearest Sentinel-1 radar acquisition is shown as "
            "all-weather context, not as a replacement for the "
            f"{preferred_metric_type.upper()} measurement."
        )

    elif preferred is not None:
        recommended_kind = (
            "preferred_metric"
        )

        recommended = (
            preferred
        )

        reason = (
            "Nearest usable "
            f"{preferred_metric_type.upper()} "
            "observation within the requested window."
        )

    elif radar is not None:
        recommended_kind = (
            "radar_fallback"
        )

        recommended = (
            radar
        )

        reason = (
            "No usable "
            f"{preferred_metric_type.upper()} "
            "observation exists within the requested window. "
            "The nearest Sentinel-1 radar acquisition is shown as "
            "all-weather context, not as an equivalent optical metric."
        )

    return FieldSatelliteTimelineResponse(
        field_id=(
            field_id
        ),
        events=[
            _event_from_observation(
                observation
            )
            for observation
            in sorted_observations
        ],
        selection=(
            SatelliteTimelineSelection(
                target_date=(
                    resolved_target_date
                ),
                preferred_metric_type=(
                    preferred_metric_type
                ),
                minimum_valid_percent=(
                    minimum_valid_percent
                ),
                search_window_days=(
                    window_days
                ),
                optical_unavailable_on_target=(
                    optical_unavailable
                ),
                preferred_metric=(
                    preferred
                ),
                radar_fallback=(
                    radar
                ),
                recommended_kind=(
                    recommended_kind
                ),
                recommended=(
                    recommended
                ),
                recommendation_reason=(
                    reason
                ),
            )
        ),
    )


def get_field_satellite_timeline(
    *,
    db: DBSession,
    field_id: UUID,
    preferred_metric_type: str,
    target_date: date | None,
    minimum_valid_percent: float,
    window_days: int,
    event_limit: int,
) -> FieldSatelliteTimelineResponse:
    start_date = None
    end_date = None

    if target_date is not None:
        start_date = (
            target_date
            - timedelta(
                days=window_days
            )
        )

        end_date = (
            target_date
            + timedelta(
                days=window_days
            )
        )

    statement = (
        select(
            SatelliteObservation
        )
        .options(
            selectinload(
                SatelliteObservation
                .metrics
            )
        )
        .where(
            SatelliteObservation
            .field_id
            == field_id
        )
        .order_by(
            SatelliteObservation
            .observed_on
            .desc(),
            SatelliteObservation
            .created_at
            .desc(),
        )
    )

    if (
        start_date is not None
        and end_date is not None
    ):
        statement = (
            statement.where(
                SatelliteObservation
                .observed_on
                >= start_date,
                SatelliteObservation
                .observed_on
                <= end_date,
            )
        )

    observations = list(
        db.scalars(
            statement.limit(
                event_limit
            )
        ).all()
    )

    return build_satellite_timeline(
        field_id=(
            field_id
        ),
        observations=(
            observations
        ),
        preferred_metric_type=(
            preferred_metric_type
        ),
        target_date=(
            target_date
        ),
        minimum_valid_percent=(
            minimum_valid_percent
        ),
        window_days=(
            window_days
        ),
    )
