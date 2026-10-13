from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

from google.cloud import storage
from pystac_client import Client
from sqlalchemy import create_engine, text

from satellite_worker.anomaly import (
    detect_metric_anomalies,
)
from satellite_worker.anomaly_rules import (
    METRIC_ANOMALY_RULES,
)
from satellite_worker.config import settings
from satellite_worker.sentinel2.processor import (
    process_metrics,
)
from satellite_worker.storage_layout import (
    satellite_metric_key,
)


ALL_METRICS = (
    "ndvi",
    "ndre",
    "ndmi",
    "gndvi",
    "evi2",
    "ndwi",
    "savi",
    "msavi",
    "bsi",
    "ndti",
    "ccci",
    "reci",
    "mcari",
)


MINIMUM_ANOMALY_VALID_PERCENT = 80.0


def _gcs_client() -> storage.Client:
    if (
        settings.gcs_credentials_path
        is not None
    ):
        return (
            storage.Client
            .from_service_account_json(
                str(
                    settings
                    .gcs_credentials_path
                ),
                project=(
                    settings
                    .gcs_project_id
                ),
            )
        )

    return storage.Client(
        project=(
            settings
            .gcs_project_id
        )
    )


def _field_context(
    engine,
    field_id: UUID,
) -> dict:
    with engine.connect() as connection:
        row = (
            connection.execute(
                text(
                    """
                    SELECT
                        u.id AS user_id,

                        fa.id AS farm_id,
                        fa.storage_slug
                            AS farm_storage_slug,

                        f.id AS field_id,
                        f.storage_slug
                            AS field_storage_slug,

                        ST_AsGeoJSON(
                            f.boundary
                        ) AS field_boundary

                    FROM fields AS f

                    JOIN farms AS fa
                      ON fa.id = f.farm_id

                    JOIN users AS u
                      ON u.id = fa.owner_user_id

                    WHERE f.id = :field_id
                    """
                ),
                {
                    "field_id":
                        field_id,
                },
            )
            .mappings()
            .first()
        )

    if row is None:
        raise RuntimeError(
            f"Field not found: {field_id}"
        )

    result = dict(
        row
    )

    boundary = result[
        "field_boundary"
    ]

    if isinstance(
        boundary,
        str,
    ):
        boundary = json.loads(
            boundary
        )

    result[
        "field_boundary"
    ] = boundary

    return result


def _incomplete_observations(
    engine,
    *,
    observation_id: UUID | None,
    limit: int,
) -> list[dict]:
    clauses = []

    params: dict = {}

    if observation_id is not None:
        clauses.append(
            "so.id = :observation_id"
        )

        params[
            "observation_id"
        ] = observation_id

    where_sql = (
        "WHERE "
        + " AND ".join(
            clauses
        )
        if clauses
        else ""
    )

    limit_sql = ""

    if limit > 0:
        limit_sql = (
            "LIMIT :limit"
        )

        params[
            "limit"
        ] = limit

    query = text(
        f"""
        SELECT
            so.id,
            so.field_id,
            so.observed_on,
            so.scene_id,
            ARRAY_AGG(
                sm.metric_type
                ORDER BY sm.metric_type
            ) FILTER (
                WHERE sm.metric_type
                IS NOT NULL
            ) AS metrics

        FROM satellite_observations
            AS so

        LEFT JOIN satellite_metrics
            AS sm
          ON sm.satellite_observation_id
             = so.id

        {where_sql}

        GROUP BY
            so.id,
            so.field_id,
            so.observed_on,
            so.scene_id

        HAVING COUNT(sm.id) < 13

        ORDER BY
            so.observed_on,
            so.id

        {limit_sql}
        """
    )

    with engine.connect() as connection:
        return [
            dict(row)
            for row in (
                connection.execute(
                    query,
                    params,
                )
                .mappings()
                .all()
            )
        ]


def _find_scene(
    *,
    catalog: Client,
    scene_id: str,
):
    items = list(
        catalog.search(
            collections=[
                "sentinel-2-l2a",
            ],
            ids=[
                scene_id,
            ],
        ).items()
    )

    if not items:
        raise RuntimeError(
            "Sentinel-2 STAC scene "
            f"not found: {scene_id}"
        )

    exact = next(
        (
            item
            for item in items
            if item.id
            == scene_id
        ),
        None,
    )

    if exact is None:
        raise RuntimeError(
            "STAC returned items, but not "
            f"the exact scene {scene_id}."
        )

    return exact


def _upload_results(
    *,
    client: storage.Client,
    bucket_name: str,
    context: dict,
    observed_on,
    observation_id: UUID,
    results: list,
) -> dict[str, str]:
    bucket = client.bucket(
        bucket_name
    )

    uploaded_keys = []

    uris: dict[
        str,
        str,
    ] = {}

    try:
        for result in results:
            metric_type = (
                result.metric_type
                .strip()
                .lower()
            )

            object_key = (
                satellite_metric_key(
                    context=context,
                    observed_on=(
                        observed_on
                    ),
                    observation_id=(
                        observation_id
                    ),
                    metric_type=(
                        metric_type
                    ),
                )
            )

            blob = bucket.blob(
                object_key
            )

            blob.upload_from_filename(
                str(
                    result
                    .raster_path
                ),
                content_type="image/tiff",
            )

            blob.reload(
                client=client
            )

            local_size = (
                result
                .raster_path
                .stat()
                .st_size
            )

            remote_size = int(
                blob.size
                or 0
            )

            if (
                local_size
                != remote_size
            ):
                raise RuntimeError(
                    "COG size mismatch "
                    f"for {metric_type}: "
                    f"local={local_size}, "
                    f"gcs={remote_size}"
                )

            uploaded_keys.append(
                object_key
            )

            uris[
                metric_type
            ] = (
                f"gs://{bucket_name}/"
                f"{object_key}"
            )

            print(
                "    uploaded "
                f"{metric_type.upper()}"
            )

    except Exception:
        for object_key in uploaded_keys:
            try:
                bucket.blob(
                    object_key
                ).delete(
                    client=client
                )
            except Exception:
                pass

        raise

    return uris


def _metric_metadata(
    result,
    analysis: dict | None,
) -> dict:
    payload = {
        "formula":
            result.formula_version,
        "calibration_methods":
            result.calibration_methods,
        "source":
            "earth-search-sentinel-2-l2a",
    }

    if analysis is not None:
        payload[
            "anomaly_analysis"
        ] = analysis

    return payload


def _save_metric_and_anomalies(
    *,
    engine,
    observation_id: UUID,
    result,
    raster_uri: str,
    zones: list,
    analysis: dict | None,
) -> None:
    metric_type = (
        result.metric_type
        .strip()
        .lower()
    )

    metric_query = text(
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

    delete_anomalies = text(
        """
        DELETE FROM satellite_anomalies
        WHERE
            satellite_observation_id =
                :observation_id
        AND index_type =
                :metric_type
        """
    )

    insert_anomaly = text(
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

    with engine.begin() as connection:
        connection.execute(
            metric_query,
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
                        _metric_metadata(
                            result,
                            analysis,
                        )
                    ),
            },
        )

        connection.execute(
            delete_anomalies,
            {
                "observation_id":
                    observation_id,
                "metric_type":
                    metric_type,
            },
        )

        for zone in zones:
            connection.execute(
                insert_anomaly,
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
                        (
                            analysis.get(
                                "method",
                                "robust_mad_metric_v1",
                            )
                            if analysis
                            else "robust_mad_metric_v1"
                        ),
                    "metadata_json":
                        json.dumps(
                            zone.metadata_json
                        ),
                },
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Fill missing Sentinel-2 metric rows for "
            "legacy NDVI-only observations without "
            "creating new observations."
        )
    )

    parser.add_argument(
        "--observation-id",
        type=UUID,
        default=None,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=0,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    args = parser.parse_args()

    engine = create_engine(
        settings.database_url
    )

    observations = (
        _incomplete_observations(
            engine,
            observation_id=(
                args.observation_id
            ),
            limit=args.limit,
        )
    )

    print(
        "Incomplete observations selected: "
        f"{len(observations)}"
    )

    if not observations:
        return

    catalog = Client.open(
        settings.earth_search_url
    )

    client = _gcs_client()

    bucket_name = (
        settings.gcs_bucket_name
    )

    failed = 0

    for index, row in enumerate(
        observations,
        start=1,
    ):
        observation_id = UUID(
            str(
                row[
                    "id"
                ]
            )
        )

        field_id = UUID(
            str(
                row[
                    "field_id"
                ]
            )
        )

        existing = {
            str(metric)
            .strip()
            .lower()
            for metric
            in (
                row[
                    "metrics"
                ]
                or []
            )
        }

        missing = tuple(
            metric
            for metric
            in ALL_METRICS
            if metric
            not in existing
        )

        print()
        print(
            "=================================="
        )
        print(
            f"[{index}/{len(observations)}]"
        )
        print(
            f"Observation: {observation_id}"
        )
        print(
            f"Date:        {row['observed_on']}"
        )
        print(
            f"Scene:       {row['scene_id']}"
        )
        print(
            "Existing:    "
            + ", ".join(
                sorted(
                    existing
                )
            )
        )
        print(
            "Missing:     "
            + ", ".join(
                missing
            )
        )

        if args.dry_run:
            continue

        try:
            context = (
                _field_context(
                    engine,
                    field_id,
                )
            )

            item = _find_scene(
                catalog=catalog,
                scene_id=str(
                    row[
                        "scene_id"
                    ]
                ),
            )

            with tempfile.TemporaryDirectory(
                prefix=(
                    "farm-legacy-metrics-"
                )
            ) as temporary:
                results = (
                    process_metrics(
                        item=item,
                        field_geometry=(
                            context[
                                "field_boundary"
                            ]
                        ),
                        output_directory=(
                            Path(
                                temporary
                            )
                        ),
                        metric_types=(
                            missing
                        ),
                    )
                )

                produced = {
                    result
                    .metric_type
                    .strip()
                    .lower()
                    for result
                    in results
                }

                not_produced = (
                    set(
                        missing
                    )
                    - produced
                )

                if not_produced:
                    print(
                        "  warning: processor "
                        "could not produce: "
                        + ", ".join(
                            sorted(
                                not_produced
                            )
                        )
                    )

                raster_uris = (
                    _upload_results(
                        client=client,
                        bucket_name=(
                            bucket_name
                        ),
                        context=context,
                        observed_on=(
                            row[
                                "observed_on"
                            ]
                        ),
                        observation_id=(
                            observation_id
                        ),
                        results=results,
                    )
                )

                for result in results:
                    metric_type = (
                        result
                        .metric_type
                        .strip()
                        .lower()
                    )

                    zones = []
                    analysis = None

                    rule = (
                        METRIC_ANOMALY_RULES
                        .get(
                            metric_type
                        )
                    )

                    if rule is not None:
                        if (
                            result
                            .valid_pixel_percent
                            < MINIMUM_ANOMALY_VALID_PERCENT
                        ):
                            analysis = {
                                "status":
                                    "skipped_low_valid_coverage",
                                "method":
                                    "robust_mad_metric_v1",
                                "metric_type":
                                    metric_type,
                                "metric_label":
                                    rule.label,
                                "direction":
                                    rule.direction,
                                "valid_pixel_percent":
                                    result.valid_pixel_percent,
                                "minimum_required_percent":
                                    MINIMUM_ANOMALY_VALID_PERCENT,
                                "zone_count":
                                    0,
                                "repaired_legacy_observation":
                                    True,
                            }

                        else:
                            anomaly_result = (
                                detect_metric_anomalies(
                                    metric_type=(
                                        metric_type
                                    ),
                                    raster_path=(
                                        result
                                        .raster_path
                                    ),
                                    field_geometry=(
                                        context[
                                            "field_boundary"
                                        ]
                                    ),
                                )
                            )

                            zones = (
                                anomaly_result
                                .zones
                            )

                            analysis = dict(
                                anomaly_result
                                .analysis
                            )

                            analysis[
                                "repaired_legacy_observation"
                            ] = True

                    _save_metric_and_anomalies(
                        engine=engine,
                        observation_id=(
                            observation_id
                        ),
                        result=result,
                        raster_uri=(
                            raster_uris[
                                metric_type
                            ]
                        ),
                        zones=zones,
                        analysis=analysis,
                    )

                    print(
                        "    saved "
                        f"{metric_type.upper()} "
                        f"({len(zones)} anomaly zones)"
                    )

        except Exception as error:
            failed += 1

            print(
                "  FAILED: "
                f"{type(error).__name__}: "
                f"{error}"
            )

    with engine.connect() as connection:
        remaining = (
            connection.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM (
                        SELECT
                            satellite_observation_id
                        FROM satellite_metrics
                        GROUP BY
                            satellite_observation_id
                        HAVING COUNT(*) <> 13
                    ) AS incomplete
                    """
                )
            )
            .scalar_one()
        )

        total_metrics = (
            connection.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM satellite_metrics
                    """
                )
            )
            .scalar_one()
        )

    print()
    print(
        "=================================="
    )
    print(
        f"Failed observations:     {failed}"
    )
    print(
        f"Incomplete observations: {remaining}"
    )
    print(
        f"Total metric rows:        {total_metrics}"
    )

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
