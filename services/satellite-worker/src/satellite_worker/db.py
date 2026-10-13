
from __future__ import annotations

import json
from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text

from satellite_worker.config import settings
engine = create_engine(
    settings.database_url,
)


def get_field_geometry(
    field_id: UUID,
) -> dict:
    query = text(
        """
        SELECT
            ST_AsGeoJSON(boundary)
                AS geometry
        FROM fields
        WHERE id = :field_id
        """
    )

    with engine.connect() as connection:
        row = (
            connection.execute(
                query,
                {
                    "field_id":
                        field_id,
                },
            )
            .mappings()
            .first()
        )

    if row is None:
        raise ValueError(
            f"Field not found: {field_id}"
        )

    geometry = row[
        "geometry"
    ]

    if isinstance(
        geometry,
        str,
    ):
        geometry = json.loads(
            geometry
        )

    return geometry


def save_satellite_observation(
    *,
    field_id: UUID,
    observed_on: date,
    scene_id: str,
    cloud_cover_percent: float | None,
    metadata_json: dict,
) -> UUID:
    """
    Upsert scene-level metadata only.

    All metric statistics, coverage, resolutions and raster URIs belong in
    satellite_metrics.
    """

    observation_id = uuid4()

    query = text(
        """
        INSERT INTO satellite_observations (
            id,
            field_id,
            observed_on,
            source,
            scene_id,
            cloud_cover_percent,
            metadata_json,
            created_at,
            updated_at
        )
        VALUES (
            :id,
            :field_id,
            :observed_on,
            'sentinel-2',
            :scene_id,
            :cloud_cover_percent,
            CAST(
                :metadata_json
                AS jsonb
            ),
            NOW(),
            NOW()
        )

        ON CONFLICT (
            field_id,
            scene_id
        )

        DO UPDATE SET
            observed_on =
                EXCLUDED.observed_on,

            cloud_cover_percent =
                EXCLUDED.cloud_cover_percent,

            metadata_json =
                EXCLUDED.metadata_json,

            updated_at =
                NOW()

        RETURNING id
        """
    )

    with engine.begin() as connection:
        return connection.execute(
            query,
            {
                "id":
                    observation_id,
                "field_id":
                    field_id,
                "observed_on":
                    observed_on,
                "scene_id":
                    scene_id,
                "cloud_cover_percent":
                    cloud_cover_percent,
                "metadata_json":
                    json.dumps(
                        metadata_json
                    ),
            },
        ).scalar_one()


def save_satellite_metrics(
    *,
    observation_id: UUID,
    results: list,
    raster_uris: dict[str, str],
) -> None:
    """
    Persist canonical metric rows using permanent GCS raster URIs.
    """

    query = text(
        """
        INSERT INTO satellite_metrics (
            id,
            satellite_observation_id,
            metric_type,
            raster_uri,
            mean,
            median,
            min,
            max,
            std,
            native_resolution_m,
            output_resolution_m,
            pixel_count,
            valid_pixel_count,
            valid_pixel_percent,
            metadata_json,
            created_at,
            updated_at
        )
        VALUES (
            :id,
            :observation_id,
            :metric_type,
            :raster_uri,
            :mean,
            :median,
            :minimum,
            :maximum,
            :std,
            :native_resolution_m,
            :output_resolution_m,
            :pixel_count,
            :valid_pixel_count,
            :valid_pixel_percent,
            CAST(
                :metadata_json
                AS jsonb
            ),
            NOW(),
            NOW()
        )

        ON CONFLICT (
            satellite_observation_id,
            metric_type
        )

        DO UPDATE SET
            raster_uri =
                EXCLUDED.raster_uri,

            mean =
                EXCLUDED.mean,

            median =
                EXCLUDED.median,

            min =
                EXCLUDED.min,

            max =
                EXCLUDED.max,

            std =
                EXCLUDED.std,

            native_resolution_m =
                EXCLUDED.native_resolution_m,

            output_resolution_m =
                EXCLUDED.output_resolution_m,

            pixel_count =
                EXCLUDED.pixel_count,

            valid_pixel_count =
                EXCLUDED.valid_pixel_count,

            valid_pixel_percent =
                EXCLUDED.valid_pixel_percent,

            metadata_json =
                EXCLUDED.metadata_json,

            updated_at =
                NOW()
        """
    )

    with engine.begin() as connection:
        for result in results:
            metric_type = (
                result.metric_type
                .strip()
                .lower()
            )

            raster_uri = (
                raster_uris.get(
                    metric_type
                )
            )

            if not raster_uri:
                raise RuntimeError(
                    "Missing permanent raster URI "
                    f"for {metric_type}."
                )

            metric_metadata = {
                "formula":
                    result.formula_version,
                "calibration_methods":
                    result.calibration_methods,
                "source":
                    "earth-search-sentinel-2-l2a",
            }

            connection.execute(
                query,
                {
                    "id":
                        uuid4(),
                    "observation_id":
                        observation_id,
                    "metric_type":
                        metric_type,
                    "raster_uri":
                        raster_uri,
                    "mean":
                        result.mean,
                    "median":
                        result.median,
                    "minimum":
                        result.minimum,
                    "maximum":
                        result.maximum,
                    "std":
                        result.std,
                    "native_resolution_m":
                        result.native_resolution_m,
                    "output_resolution_m":
                        result.output_resolution_m,
                    "pixel_count":
                        result.pixel_count,
                    "valid_pixel_count":
                        result.valid_pixel_count,
                    "valid_pixel_percent":
                        result.valid_pixel_percent,
                    "metadata_json":
                        json.dumps(
                            metric_metadata
                        ),
                },
            )


def replace_satellite_anomalies(
    *,
    observation_id: UUID,
    metric_type: str,
    zones: list,
    analysis_json: dict,
) -> None:
    metric_type = (
        metric_type
        .strip()
        .lower()
    )

    if not metric_type:
        raise ValueError(
            "metric_type cannot be empty."
        )

    detection_method = (
        analysis_json.get(
            "method",
            "robust_mad_metric_v1",
        )
    )

    delete_query = text(
        """
        DELETE FROM satellite_anomalies

        WHERE satellite_observation_id =
            :observation_id

        AND index_type =
            :metric_type
        """
    )

    insert_query = text(
        """
        INSERT INTO satellite_anomalies (
            id,
            satellite_observation_id,
            zone_index,
            index_type,
            anomaly_type,
            severity,
            geometry,
            pixel_count,
            area_sqm,
            area_acres,
            zone_mean_value,
            zone_min_value,
            zone_max_value,
            field_mean_value,
            field_median_value,
            threshold_value,
            difference_from_field,
            percent_difference,
            detection_method,
            metadata_json,
            created_at,
            updated_at
        )
        VALUES (
            :id,
            :observation_id,
            :zone_index,
            :metric_type,
            :anomaly_type,
            :severity,

            ST_Multi(
                ST_SetSRID(
                    ST_GeomFromGeoJSON(
                        :geometry_json
                    ),
                    4326
                )
            ),

            :pixel_count,
            :area_sqm,
            :area_acres,
            :zone_mean_value,
            :zone_min_value,
            :zone_max_value,
            :field_mean_value,
            :field_median_value,
            :threshold_value,
            :difference_from_field,
            :percent_difference,
            :detection_method,

            CAST(
                :metadata_json
                AS jsonb
            ),

            NOW(),
            NOW()
        )
        """
    )

    update_metric_query = text(
        """
        UPDATE satellite_metrics

        SET
            metadata_json =
                jsonb_set(
                    COALESCE(
                        metadata_json,
                        '{}'::jsonb
                    ),
                    '{anomaly_analysis}',
                    CAST(
                        :analysis_json
                        AS jsonb
                    ),
                    true
                ),

            updated_at =
                NOW()

        WHERE satellite_observation_id =
            :observation_id

        AND metric_type =
            :metric_type
        """
    )

    with engine.begin() as connection:
        metric_exists = connection.execute(
            text(
                """
                SELECT 1
                FROM satellite_metrics
                WHERE satellite_observation_id =
                    :observation_id
                  AND metric_type =
                    :metric_type
                """
            ),
            {
                "observation_id":
                    observation_id,
                "metric_type":
                    metric_type,
            },
        ).scalar_one_or_none()

        if metric_exists is None:
            raise RuntimeError(
                "Cannot save anomaly analysis "
                f"before metric row exists: {metric_type}"
            )

        connection.execute(
            delete_query,
            {
                "observation_id":
                    observation_id,
                "metric_type":
                    metric_type,
            },
        )

        for zone in zones:
            connection.execute(
                insert_query,
                {
                    "id":
                        uuid4(),
                    "observation_id":
                        observation_id,
                    "zone_index":
                        zone.zone_index,
                    "metric_type":
                        metric_type,
                    "anomaly_type":
                        zone.anomaly_type,
                    "severity":
                        zone.severity,
                    "geometry_json":
                        json.dumps(
                            zone.geometry
                        ),
                    "pixel_count":
                        zone.pixel_count,
                    "area_sqm":
                        zone.area_sqm,
                    "area_acres":
                        zone.area_acres,
                    "zone_mean_value":
                        zone.zone_mean_value,
                    "zone_min_value":
                        zone.zone_min_value,
                    "zone_max_value":
                        zone.zone_max_value,
                    "field_mean_value":
                        zone.field_mean_value,
                    "field_median_value":
                        zone.field_median_value,
                    "threshold_value":
                        zone.threshold_value,
                    "difference_from_field":
                        zone.difference_from_field,
                    "percent_difference":
                        zone.percent_difference,
                    "detection_method":
                        detection_method,
                    "metadata_json":
                        json.dumps(
                            zone.metadata_json
                        ),
                },
            )

        connection.execute(
            update_metric_query,
            {
                "observation_id":
                    observation_id,
                "metric_type":
                    metric_type,
                "analysis_json":
                    json.dumps(
                        analysis_json
                    ),
            },
        )


def list_satellite_metric_rasters_for_backfill(
    *,
    field_id: UUID | None = None,
    observation_id: UUID | None = None,
    metric_types: tuple[str, ...] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 0,
    only_missing: bool = False,
) -> list[dict]:
    clauses = [
        "sm.raster_uri IS NOT NULL",
    ]

    params: dict = {}

    if field_id is not None:
        clauses.append(
            "so.field_id = :field_id"
        )

        params[
            "field_id"
        ] = field_id

    if observation_id is not None:
        clauses.append(
            "so.id = :observation_id"
        )

        params[
            "observation_id"
        ] = observation_id

    if start_date is not None:
        clauses.append(
            "so.observed_on >= :start_date"
        )

        params[
            "start_date"
        ] = start_date

    if end_date is not None:
        clauses.append(
            "so.observed_on <= :end_date"
        )

        params[
            "end_date"
        ] = end_date

    normalized_metric_types = tuple(
        metric_type.strip().lower()
        for metric_type in (
            metric_types
            or ()
        )
        if metric_type.strip()
    )

    if normalized_metric_types:
        placeholders = []

        for (
            index,
            metric_type,
        ) in enumerate(
            normalized_metric_types
        ):
            parameter_name = (
                f"metric_type_{index}"
            )

            placeholders.append(
                f":{parameter_name}"
            )

            params[
                parameter_name
            ] = metric_type

        clauses.append(
            "sm.metric_type IN ("
            + ", ".join(
                placeholders
            )
            + ")"
        )

    if only_missing:
        clauses.append(
            """
            NOT (
                COALESCE(
                    sm.metadata_json,
                    '{}'::jsonb
                )
                ? 'anomaly_analysis'
            )
            """
        )

    where_sql = (
        "\n        AND "
        .join(
            clauses
        )
    )

    limit_sql = ""

    if limit > 0:
        limit_sql = (
            "\n        LIMIT :limit"
        )

        params[
            "limit"
        ] = limit

    query = text(
        f"""
        SELECT
            so.id
                AS observation_id,

            so.field_id
                AS field_id,

            f.name
                AS field_name,

            so.observed_on
                AS observed_on,

            so.scene_id
                AS scene_id,

            sm.metric_type
                AS metric_type,

            sm.raster_uri
                AS raster_uri,

            sm.valid_pixel_percent
                AS valid_pixel_percent

        FROM satellite_metrics
            AS sm

        JOIN satellite_observations
            AS so
            ON so.id =
                sm.satellite_observation_id

        JOIN fields
            AS f
            ON f.id =
                so.field_id

        WHERE
            {where_sql}

        ORDER BY
            so.observed_on,
            so.id,
            sm.metric_type
        {limit_sql}
        """
    )

    with engine.connect() as connection:
        rows = (
            connection.execute(
                query,
                params,
            )
            .mappings()
            .all()
        )

    return [
        dict(row)
        for row in rows
    ]
