"""Compute quality-filtered satellite and spatial anomaly changes."""

from __future__ import annotations

import json
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select, text

from sqlalchemy.orm import Session as DBSession
from app.models.satellite_metric import SatelliteMetric
from app.models.satellite_observation import SatelliteObservation
from app.schemas.satellite_change import (
    FieldSatelliteChangeResponse,
    SatelliteChangeAnomalySummary,
    SatelliteChangeMode,
    SatelliteChangeObservation,
    SatelliteChangeScalarSummary,
)


SQUARE_METRES_PER_ACRE = 4046.8564224

PERCENT_CHANGE_MINIMUM_BASELINE_ABS = 0.05

PERCENT_CHANGE_UNSUITABLE_METRICS = {
    "sar_vv_db",
    "sar_vh_db",
    "lst_c",
}

SPATIAL_PERSISTENCE_BASIS = (
    "same_anomaly_type_overlap"
)

DEFAULT_PIXEL_CHANGE_DISPLAY_MAX = {
    "ndvi": 0.30,
    "ndre": 0.25,
    "ndmi": 0.30,
    "gndvi": 0.30,
    "evi2": 0.35,
    "ndwi": 0.35,
    "savi": 0.35,
    "msavi": 0.35,
    "bsi": 0.30,
    "ndti": 0.25,
    "ccci": 0.50,
    "reci": 1.00,
    "mcari": 0.20,
    "sar_vv_db": 5.0,
    "sar_vh_db": 5.0,
    "sar_vv_vh_ratio": 5.0,
    "sar_rvi": 0.50,
    "lst_c": 8.0,
}


DEFAULT_PIXEL_CHANGE_THRESHOLDS = {
    "ndvi": 0.03,
    "ndre": 0.03,
    "ndmi": 0.03,
    "gndvi": 0.03,
    "evi2": 0.03,
    "ndwi": 0.03,
    "savi": 0.03,
    "msavi": 0.03,
    "bsi": 0.03,
    "ndti": 0.03,
    "ccci": 0.05,
    "reci": 0.10,
    "mcari": 0.02,
    "sar_vv_db": 1.0,
    "sar_vh_db": 1.0,
    "sar_vv_vh_ratio": 0.5,
    "sar_rvi": 0.05,
    "lst_c": 1.0,
}


def _radar_geometry(
    observation: SatelliteObservation,
) -> tuple[
    str | None,
    int | None,
    str | None,
]:
    if not observation.source.startswith(
        "sentinel-1"
    ):
        return (
            None,
            None,
            None,
        )

    metadata = (
        observation.metadata_json
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

    return (
        orbit_state,
        relative_orbit,
        platform,
    )


def default_pixel_change_threshold(
    metric_type: str,
) -> float:
    return float(
        DEFAULT_PIXEL_CHANGE_THRESHOLDS.get(
            metric_type,
            0.03,
        )
    )


def default_pixel_change_display_max(
    metric_type: str,
) -> float:
    return float(
        DEFAULT_PIXEL_CHANGE_DISPLAY_MAX.get(
            metric_type,
            0.30,
        )
    )


def _metric_statement(
    *,
    field_id: UUID,
    metric_type: str,
    minimum_valid_percent: float,
    orbit_state: str | None = None,
    relative_orbit: int | None = None,
):
    statement = (
        select(
            SatelliteObservation,
            SatelliteMetric,
        )
        .join(
            SatelliteMetric,
            SatelliteMetric.satellite_observation_id
            == SatelliteObservation.id,
        )
        .where(
            SatelliteObservation.field_id
            == field_id,
            SatelliteMetric.metric_type
            == metric_type,
            SatelliteMetric.raster_uri.is_not(
                None
            ),
            or_(
                SatelliteMetric.valid_pixel_percent.is_(
                    None
                ),
                SatelliteMetric.valid_pixel_percent
                >= minimum_valid_percent,
            ),
        )
    )

    if orbit_state is not None:
        statement = statement.where(
            func.lower(
                SatelliteObservation
                .metadata_json[
                    "orbit_state"
                ]
                .astext
            )
            == orbit_state
        )

    if relative_orbit is not None:
        statement = statement.where(
            SatelliteObservation
            .metadata_json[
                "relative_orbit"
            ]
            .astext
            == str(
                relative_orbit
            )
        )

    return statement


def _latest_metric(
    *,
    db: DBSession,
    field_id: UUID,
    metric_type: str,
    minimum_valid_percent: float,
    on_or_before: date | None,
) -> tuple[
    SatelliteObservation,
    SatelliteMetric,
] | None:
    statement = _metric_statement(
        field_id=field_id,
        metric_type=metric_type,
        minimum_valid_percent=(
            minimum_valid_percent
        ),
    )

    if on_or_before is not None:
        statement = statement.where(
            SatelliteObservation.observed_on
            <= on_or_before
        )

    return db.execute(
        statement.order_by(
            SatelliteObservation.observed_on.desc(),
            SatelliteMetric.valid_pixel_percent.desc().nullslast(),
            SatelliteObservation.created_at.desc(),
        )
        .limit(
            1
        )
    ).first()


def _previous_metric(
    *,
    db: DBSession,
    field_id: UUID,
    metric_type: str,
    minimum_valid_percent: float,
    before_date: date,
    orbit_state: str | None = None,
    relative_orbit: int | None = None,
) -> tuple[
    SatelliteObservation,
    SatelliteMetric,
] | None:
    return db.execute(
        _metric_statement(
            field_id=field_id,
            metric_type=metric_type,
            minimum_valid_percent=(
                minimum_valid_percent
            ),
            orbit_state=(
                orbit_state
            ),
            relative_orbit=(
                relative_orbit
            ),
        )
        .where(
            SatelliteObservation.observed_on
            < before_date
        )
        .order_by(
            SatelliteObservation.observed_on.desc(),
            SatelliteMetric.valid_pixel_percent.desc().nullslast(),
            SatelliteObservation.created_at.desc(),
        )
        .limit(
            1
        )
    ).first()


def _nearest_metric_to_date(
    *,
    db: DBSession,
    field_id: UUID,
    metric_type: str,
    minimum_valid_percent: float,
    target_date: date,
    tolerance_days: int,
    before_date: date,
    orbit_state: str | None = None,
    relative_orbit: int | None = None,
) -> tuple[
    SatelliteObservation,
    SatelliteMetric,
] | None:
    lower = (
        target_date
        - timedelta(
            days=tolerance_days
        )
    )

    upper = min(
        target_date
        + timedelta(
            days=tolerance_days
        ),
        before_date
        - timedelta(
            days=1
        ),
    )

    if upper < lower:
        return None

    distance = func.abs(
        SatelliteObservation.observed_on
        - target_date
    )

    return db.execute(
        _metric_statement(
            field_id=field_id,
            metric_type=metric_type,
            minimum_valid_percent=(
                minimum_valid_percent
            ),
            orbit_state=(
                orbit_state
            ),
            relative_orbit=(
                relative_orbit
            ),
        )
        .where(
            SatelliteObservation.observed_on
            >= lower,
            SatelliteObservation.observed_on
            <= upper,
        )
        .order_by(
            distance,
            SatelliteObservation.observed_on.desc(),
            SatelliteMetric.valid_pixel_percent.desc().nullslast(),
        )
        .limit(
            1
        )
    ).first()


def _to_observation(
    row: tuple[
        SatelliteObservation,
        SatelliteMetric,
    ]
    | None,
) -> SatelliteChangeObservation | None:
    if row is None:
        return None

    observation, metric = row

    (
        orbit_state,
        relative_orbit,
        platform,
    ) = _radar_geometry(
        observation
    )

    return SatelliteChangeObservation(
        observation_id=observation.id,
        observed_on=observation.observed_on,
        source=observation.source,
        scene_id=observation.scene_id,
        orbit_state=orbit_state,
        relative_orbit=relative_orbit,
        platform=platform,
        metric_type=metric.metric_type,
        valid_pixel_percent=(
            metric.valid_pixel_percent
        ),
        mean=metric.mean,
        median=metric.median,
        minimum=metric.min,
        maximum=metric.max,
        std=metric.std,
        raster_uri=metric.raster_uri,
        native_resolution_m=(
            metric.native_resolution_m
        ),
        output_resolution_m=(
            metric.output_resolution_m
        ),
    )


def _absolute_change(
    before: float | None,
    after: float | None,
) -> float | None:
    if (
        before is None
        or after is None
    ):
        return None

    return float(
        after
        - before
    )


def _percent_change(
    *,
    metric_type: str,
    before: float | None,
    after: float | None,
) -> float | None:
    if (
        metric_type
        in PERCENT_CHANGE_UNSUITABLE_METRICS
    ):
        return None

    if (
        before is None
        or after is None
    ):
        return None

    if (
        abs(
            before
        )
        < PERCENT_CHANGE_MINIMUM_BASELINE_ABS
    ):
        return None

    return float(
        (
            after
            - before
        )
        / abs(
            before
        )
        * 100.0
    )


def _scalar_summary(
    *,
    metric_type: str,
    before: SatelliteChangeObservation | None,
    after: SatelliteChangeObservation | None,
) -> SatelliteChangeScalarSummary:
    if (
        before is None
        or after is None
    ):
        return SatelliteChangeScalarSummary(
            days_between=None,
            mean_change=None,
            mean_percent_change=None,
            median_change=None,
            median_percent_change=None,
        )

    return SatelliteChangeScalarSummary(
        days_between=(
            after.observed_on
            - before.observed_on
        ).days,
        mean_change=(
            _absolute_change(
                before.mean,
                after.mean,
            )
        ),
        mean_percent_change=(
            _percent_change(
                metric_type=metric_type,
                before=before.mean,
                after=after.mean,
            )
        ),
        median_change=(
            _absolute_change(
                before.median,
                after.median,
            )
        ),
        median_percent_change=(
            _percent_change(
                metric_type=metric_type,
                before=before.median,
                after=after.median,
            )
        ),
    )


def _sqm_to_acres(
    area_sqm: float,
) -> float:
    return float(
        area_sqm
        / SQUARE_METRES_PER_ACRE
    )


def _decode_geojson(
    value: str | None,
) -> dict | None:
    if value is None:
        return None

    return json.loads(
        value
    )


def _empty_anomaly_summary(
    *,
    before_area_sqm: float | None,
    after_area_sqm: float | None,
) -> SatelliteChangeAnomalySummary:
    return SatelliteChangeAnomalySummary(
        persistence_basis=(
            SPATIAL_PERSISTENCE_BASIS
        ),
        before_anomaly_area_sqm=(
            before_area_sqm
        ),
        before_anomaly_area_acres=(
            _sqm_to_acres(
                before_area_sqm
            )
            if before_area_sqm
            is not None
            else None
        ),
        after_anomaly_area_sqm=(
            after_area_sqm
        ),
        after_anomaly_area_acres=(
            _sqm_to_acres(
                after_area_sqm
            )
            if after_area_sqm
            is not None
            else None
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


def _anomaly_area(
    *,
    db: DBSession,
    observation_id: UUID,
    metric_type: str,
) -> float:
    row = db.execute(
        text(
            """
            SELECT
                COALESCE(
                    SUM(area_sqm),
                    0.0
                ) AS area_sqm

            FROM satellite_anomalies

            WHERE
                satellite_observation_id
                    = :observation_id
                AND index_type
                    = :metric_type
            """
        ),
        {
            "observation_id":
                observation_id,
            "metric_type":
                metric_type,
        },
    ).mappings().one()

    return float(
        row[
            "area_sqm"
        ]
        or 0.0
    )


def _anomaly_spatial_summary(
    *,
    db: DBSession,
    metric_type: str,
    before: SatelliteChangeObservation | None,
    after: SatelliteChangeObservation | None,
) -> SatelliteChangeAnomalySummary:
    if metric_type.startswith(
        "sar_"
    ):
        return SatelliteChangeAnomalySummary(
            persistence_basis=(
                "radar_anomaly_rules_not_enabled"
            ),
            before_anomaly_area_sqm=None,
            before_anomaly_area_acres=None,
            after_anomaly_area_sqm=None,
            after_anomaly_area_acres=None,
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

    before_area = (
        _anomaly_area(
            db=db,
            observation_id=(
                before.observation_id
            ),
            metric_type=metric_type,
        )
        if before is not None
        else None
    )

    after_area = (
        _anomaly_area(
            db=db,
            observation_id=(
                after.observation_id
            ),
            metric_type=metric_type,
        )
        if after is not None
        else None
    )

    if (
        before is None
        or after is None
    ):
        return _empty_anomaly_summary(
            before_area_sqm=(
                before_area
            ),
            after_area_sqm=(
                after_area
            ),
        )

    row = db.execute(
        text(
            """
            WITH before_by_type AS (
                SELECT
                    anomaly_type,
                    ST_UnaryUnion(
                        ST_Collect(
                            ST_MakeValid(
                                geometry
                            )
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
                            ST_MakeValid(
                                geometry
                            )
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
                        ST_Collect(
                            geom
                        )
                    ) AS geom

                FROM before_by_type
            ),

            after_union AS (
                SELECT
                    ST_UnaryUnion(
                        ST_Collect(
                            geom
                        )
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
                        ST_Collect(
                            geom
                        )
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
        ),
        {
            "before_observation_id":
                before.observation_id,
            "after_observation_id":
                after.observation_id,
            "metric_type":
                metric_type,
        },
    ).mappings().one()

    persistent_sqm = float(
        row[
            "persistent_area_sqm"
        ]
        or 0.0
    )

    resolved_sqm = float(
        row[
            "resolved_area_sqm"
        ]
        or 0.0
    )

    new_sqm = float(
        row[
            "new_area_sqm"
        ]
        or 0.0
    )

    return SatelliteChangeAnomalySummary(
        persistence_basis=(
            SPATIAL_PERSISTENCE_BASIS
        ),
        before_anomaly_area_sqm=float(
            row[
                "before_area_sqm"
            ]
            or 0.0
        ),
        before_anomaly_area_acres=(
            _sqm_to_acres(
                float(
                    row[
                        "before_area_sqm"
                    ]
                    or 0.0
                )
            )
        ),
        after_anomaly_area_sqm=float(
            row[
                "after_area_sqm"
            ]
            or 0.0
        ),
        after_anomaly_area_acres=(
            _sqm_to_acres(
                float(
                    row[
                        "after_area_sqm"
                    ]
                    or 0.0
                )
            )
        ),
        persistent_area_sqm=(
            persistent_sqm
        ),
        persistent_area_acres=(
            _sqm_to_acres(
                persistent_sqm
            )
        ),
        resolved_area_sqm=(
            resolved_sqm
        ),
        resolved_area_acres=(
            _sqm_to_acres(
                resolved_sqm
            )
        ),
        new_area_sqm=(
            new_sqm
        ),
        new_area_acres=(
            _sqm_to_acres(
                new_sqm
            )
        ),
        persistent_geometry=(
            _decode_geojson(
                row[
                    "persistent_geojson"
                ]
            )
        ),
        resolved_geometry=(
            _decode_geojson(
                row[
                    "resolved_geojson"
                ]
            )
        ),
        new_geometry=(
            _decode_geojson(
                row[
                    "new_geojson"
                ]
            )
        ),
    )


def _status(
    *,
    before: SatelliteChangeObservation | None,
    after: SatelliteChangeObservation | None,
) -> str:
    if after is None:
        return "missing_current"

    if before is None:
        return "missing_baseline"

    return "complete"


def build_field_satellite_change(
    *,
    db: DBSession,
    field_id: UUID,
    metric_type: str,
    mode: SatelliteChangeMode,
    requested_to_date: date | None,
    requested_from_date: date | None,
    crop_cycle_id: UUID | None,
    crop_reference_date: date | None,
    minimum_valid_percent: float,
    date_tolerance_days: int,
    pixel_change_threshold: float | None,
) -> FieldSatelliteChangeResponse:
    current_row = _latest_metric(
        db=db,
        field_id=field_id,
        metric_type=metric_type,
        minimum_valid_percent=(
            minimum_valid_percent
        ),
        on_or_before=(
            requested_to_date
        ),
    )

    after = _to_observation(
        current_row
    )

    baseline_target = None

    before_row = None

    radar_orbit_state = None
    radar_relative_orbit = None

    if (
        current_row is not None
        and metric_type.startswith(
            "sar_"
        )
    ):
        (
            radar_orbit_state,
            radar_relative_orbit,
            _,
        ) = _radar_geometry(
            current_row[
                0
            ]
        )

    # Radar baseline comparisons need a complete, comparable geometry.
    # Without both fields, comparing to an arbitrary pass is misleading.
    radar_geometry_complete = (
        bool(radar_orbit_state)
        and radar_relative_orbit is not None
    )

    if (
        after is not None
        and (
            not metric_type.startswith("sar_")
            or radar_geometry_complete
        )
    ):
        if mode == "previous":
            before_row = (
                _previous_metric(
                    db=db,
                    field_id=field_id,
                    metric_type=metric_type,
                    minimum_valid_percent=(
                        minimum_valid_percent
                    ),
                    before_date=(
                        after.observed_on
                    ),
                    orbit_state=(
                        radar_orbit_state
                    ),
                    relative_orbit=(
                        radar_relative_orbit
                    ),
                )
            )

        else:
            if mode == "crop_start":
                baseline_target = (
                    crop_reference_date
                )

            elif mode == "days_7":
                baseline_target = (
                    after.observed_on
                    - timedelta(
                        days=7
                    )
                )

            elif mode == "days_14":
                baseline_target = (
                    after.observed_on
                    - timedelta(
                        days=14
                    )
                )

            elif mode == "days_30":
                baseline_target = (
                    after.observed_on
                    - timedelta(
                        days=30
                    )
                )

            elif mode == "custom":
                baseline_target = (
                    requested_from_date
                )

            if baseline_target is not None:
                before_row = (
                    _nearest_metric_to_date(
                        db=db,
                        field_id=field_id,
                        metric_type=metric_type,
                        minimum_valid_percent=(
                            minimum_valid_percent
                        ),
                        target_date=(
                            baseline_target
                        ),
                        tolerance_days=(
                            date_tolerance_days
                        ),
                        before_date=(
                            after.observed_on
                        ),
                        orbit_state=(
                            radar_orbit_state
                        ),
                        relative_orbit=(
                            radar_relative_orbit
                        ),
                    )
                )

    before = _to_observation(
        before_row
    )

    resolved_threshold = (
        float(
            pixel_change_threshold
        )
        if pixel_change_threshold
        is not None
        else default_pixel_change_threshold(
            metric_type
        )
    )

    return FieldSatelliteChangeResponse(
        field_id=field_id,
        metric_type=metric_type,
        mode=mode,
        status=_status(
            before=before,
            after=after,
        ),
        requested_to_date=(
            requested_to_date
        ),
        requested_from_date=(
            requested_from_date
        ),
        baseline_target_date=(
            baseline_target
        ),
        crop_cycle_id=(
            crop_cycle_id
        ),
        crop_reference_date=(
            crop_reference_date
        ),
        minimum_valid_percent=(
            minimum_valid_percent
        ),
        date_tolerance_days=(
            date_tolerance_days
        ),
        pixel_change_threshold=(
            resolved_threshold
        ),
        pixel_change_display_max=(
            default_pixel_change_display_max(
                metric_type
            )
        ),
        before=before,
        after=after,
        scalar=_scalar_summary(
            metric_type=metric_type,
            before=before,
            after=after,
        ),
        anomalies=(
            _anomaly_spatial_summary(
                db=db,
                metric_type=metric_type,
                before=before,
                after=after,
            )
        ),
    )
