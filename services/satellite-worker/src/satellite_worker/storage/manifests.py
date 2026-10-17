"""Persist satellite observation recovery metadata alongside COGs."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import text

from satellite_worker.persistence.connection import engine
from satellite_worker.storage.gcs import gcs_bucket
from satellite_worker.storage.layout import (
    STORAGE_LAYOUT_VERSION,
    farm_manifest_key,
    field_manifest_key,
    satellite_prefix,
    user_manifest_key,
)


def _json_default(
    value,
):
    if isinstance(
        value,
        (
            datetime,
            date,
        ),
    ):
        return value.isoformat()

    if isinstance(
        value,
        UUID,
    ):
        return str(value)

    raise TypeError(
        "Unsupported JSON type: "
        f"{type(value).__name__}"
    )


def _write_json(
    *,
    object_key: str,
    payload: dict,
) -> None:
    raw = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        default=_json_default,
    )

    gcs_bucket().blob(
        object_key
    ).upload_from_string(
        raw,
        content_type="application/json",
    )


def write_hierarchy_manifests(
    context: dict,
) -> None:
    now = datetime.now(
        timezone.utc
    ).isoformat()

    _write_json(
        object_key="storage-layout.json",
        payload={
            "schema":
                "farm-platform-object-storage",
            "storage_layout_version":
                STORAGE_LAYOUT_VERSION,
            "root_prefix":
                "users/",
            "generated_at":
                now,
            "note": (
                "PostgreSQL is the operational database. "
                "These manifests make object data portable "
                "and recoverable."
            ),
        },
    )

    _write_json(
        object_key=user_manifest_key(
            context
        ),
        payload={
            "manifest_type":
                "user",
            "storage_layout_version":
                STORAGE_LAYOUT_VERSION,
            "user_id":
                str(
                    context[
                        "user_id"
                    ]
                ),
            "preferred_language":
                context.get(
                    "preferred_language"
                ),
            "updated_at":
                now,
        },
    )

    _write_json(
        object_key=farm_manifest_key(
            context
        ),
        payload={
            "manifest_type":
                "farm",
            "storage_layout_version":
                STORAGE_LAYOUT_VERSION,
            "user_id":
                str(
                    context[
                        "user_id"
                    ]
                ),
            "farm_id":
                str(
                    context[
                        "farm_id"
                    ]
                ),
            "name":
                context.get(
                    "farm_name"
                ),
            "storage_slug":
                context.get(
                    "farm_storage_slug"
                ),
            "location_name":
                context.get(
                    "farm_location_name"
                ),
            "created_at":
                context.get(
                    "farm_created_at"
                ),
            "updated_at":
                context.get(
                    "farm_updated_at"
                ),
        },
    )

    _write_json(
        object_key=field_manifest_key(
            context
        ),
        payload={
            "manifest_type":
                "field",
            "storage_layout_version":
                STORAGE_LAYOUT_VERSION,
            "user_id":
                str(
                    context[
                        "user_id"
                    ]
                ),
            "farm_id":
                str(
                    context[
                        "farm_id"
                    ]
                ),
            "field_id":
                str(
                    context[
                        "field_id"
                    ]
                ),
            "name":
                context.get(
                    "field_name"
                ),
            "storage_slug":
                context.get(
                    "field_storage_slug"
                ),
            "boundary":
                context.get(
                    "field_boundary"
                ),
            "created_at":
                context.get(
                    "field_created_at"
                ),
            "updated_at":
                context.get(
                    "field_updated_at"
                ),
        },
    )


def write_satellite_manifest_from_database(
    *,
    context: dict,
    observation_id: UUID,
) -> None:
    """
    Write one self-contained recovery manifest for a satellite observation.

    Scene metadata is read from satellite_observations.
    Every metric result is read from satellite_metrics.
    Spatial anomaly results are read from satellite_anomalies.
    """

    observation_query = text(
        """
        SELECT
            id,
            field_id,
            observed_on,
            source,
            scene_id,
            cloud_cover_percent,
            metadata_json,
            created_at,
            updated_at

        FROM satellite_observations

        WHERE id =
            :observation_id
        """
    )

    metric_query = text(
        """
        SELECT
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

        FROM satellite_metrics

        WHERE
            satellite_observation_id =
                :observation_id

        ORDER BY
            metric_type
        """
    )

    anomaly_query = text(
        """
        SELECT
            id,
            zone_index,
            index_type,
            anomaly_type,
            severity,

            ST_AsGeoJSON(
                geometry
            ) AS geometry,

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

        FROM satellite_anomalies

        WHERE
            satellite_observation_id =
                :observation_id

        ORDER BY
            index_type,
            zone_index
        """
    )

    with engine.connect() as connection:
        observation = (
            connection.execute(
                observation_query,
                {
                    "observation_id":
                        observation_id,
                },
            )
            .mappings()
            .first()
        )

        metrics = (
            connection.execute(
                metric_query,
                {
                    "observation_id":
                        observation_id,
                },
            )
            .mappings()
            .all()
        )

        anomalies = (
            connection.execute(
                anomaly_query,
                {
                    "observation_id":
                        observation_id,
                },
            )
            .mappings()
            .all()
        )

    if observation is None:
        raise RuntimeError(
            "Satellite observation "
            f"{observation_id} not found."
        )

    observed_on = observation[
        "observed_on"
    ]

    write_hierarchy_manifests(
        context
    )

    metrics_payload: dict = {}

    for row in metrics:
        metric_type = str(
            row[
                "metric_type"
            ]
        )

        metadata = (
            row[
                "metadata_json"
            ]
            or {}
        )

        metrics_payload[
            metric_type
        ] = {
            "file":
                f"{metric_type}.tif",
            "raster_uri":
                row[
                    "raster_uri"
                ],
            "mean":
                row["mean"],
            "median":
                row["median"],
            "min":
                row["min"],
            "max":
                row["max"],
            "std":
                row["std"],
            "native_resolution_m":
                row[
                    "native_resolution_m"
                ],
            "output_resolution_m":
                row[
                    "output_resolution_m"
                ],
            "pixel_count":
                row[
                    "pixel_count"
                ],
            "valid_pixel_count":
                row[
                    "valid_pixel_count"
                ],
            "valid_pixel_percent":
                row[
                    "valid_pixel_percent"
                ],
            "anomaly_analysis":
                metadata.get(
                    "anomaly_analysis"
                ),
            "metadata":
                metadata,
        }

    anomaly_payload = []

    for row in anomalies:
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

        anomaly_payload.append(
            {
                "id":
                    str(
                        row[
                            "id"
                        ]
                    ),
                "metric_type":
                    row[
                        "index_type"
                    ],
                "zone_index":
                    row[
                        "zone_index"
                    ],
                "anomaly_type":
                    row[
                        "anomaly_type"
                    ],
                "severity":
                    row[
                        "severity"
                    ],
                "geometry":
                    geometry,
                "pixel_count":
                    row[
                        "pixel_count"
                    ],
                "area_sqm":
                    row[
                        "area_sqm"
                    ],
                "area_acres":
                    row[
                        "area_acres"
                    ],
                "zone_mean_value":
                    row[
                        "zone_mean_value"
                    ],
                "zone_min_value":
                    row[
                        "zone_min_value"
                    ],
                "zone_max_value":
                    row[
                        "zone_max_value"
                    ],
                "field_mean_value":
                    row[
                        "field_mean_value"
                    ],
                "field_median_value":
                    row[
                        "field_median_value"
                    ],
                "threshold_value":
                    row[
                        "threshold_value"
                    ],
                "difference_from_field":
                    row[
                        "difference_from_field"
                    ],
                "percent_difference":
                    row[
                        "percent_difference"
                    ],
                "detection_method":
                    row[
                        "detection_method"
                    ],
                "metadata":
                    row[
                        "metadata_json"
                    ],
            }
        )

    manifest_key = (
        f"{satellite_prefix(context=context, observed_on=observed_on, observation_id=observation_id)}"
        "/manifest.json"
    )

    _write_json(
        object_key=manifest_key,
        payload={
            "manifest_type":
                "satellite_observation",
            "storage_layout_version":
                STORAGE_LAYOUT_VERSION,
            "observation_id":
                str(
                    observation[
                        "id"
                    ]
                ),
            "user_id":
                str(
                    context[
                        "user_id"
                    ]
                ),
            "farm_id":
                str(
                    context[
                        "farm_id"
                    ]
                ),
            "field_id":
                str(
                    context[
                        "field_id"
                    ]
                ),
            "observed_on":
                observed_on,
            "source":
                observation[
                    "source"
                ],
            "scene_id":
                observation[
                    "scene_id"
                ],
            "cloud_cover_percent":
                observation[
                    "cloud_cover_percent"
                ],
            "metrics":
                metrics_payload,
            "anomalies":
                anomaly_payload,
            "metadata":
                observation[
                    "metadata_json"
                ],
            "created_at":
                observation[
                    "created_at"
                ],
            "updated_at":
                observation[
                    "updated_at"
                ],
            "manifest_generated_at":
                datetime.now(
                    timezone.utc
                ),
        },
    )
