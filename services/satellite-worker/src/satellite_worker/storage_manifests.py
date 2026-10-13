
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import text

from satellite_worker.db import engine
from satellite_worker.gcs_client import (
    gcs_bucket,
)
from satellite_worker.storage_layout import (
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
        f"Unsupported JSON type: "
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
            "schema": "farm-platform-object-storage",
            "storage_layout_version":
                STORAGE_LAYOUT_VERSION,
            "root_prefix": "users/",
            "generated_at": now,
            "note": (
                "PostgreSQL is the operational database. "
                "These manifests make object data portable and recoverable."
            ),
        },
    )

    _write_json(
        object_key=user_manifest_key(
            context
        ),
        payload={
            "manifest_type": "user",
            "storage_layout_version":
                STORAGE_LAYOUT_VERSION,
            "user_id": str(
                context[
                    "user_id"
                ]
            ),
            "name": context.get(
                "user_name"
            ),
            "phone_e164": context.get(
                "phone_e164"
            ),
            "preferred_language":
                context.get(
                    "preferred_language"
                ),
            "private_pii": True,
            "updated_at": now,
        },
    )

    _write_json(
        object_key=farm_manifest_key(
            context
        ),
        payload={
            "manifest_type": "farm",
            "storage_layout_version":
                STORAGE_LAYOUT_VERSION,
            "user_id": str(
                context[
                    "user_id"
                ]
            ),
            "farm_id": str(
                context[
                    "farm_id"
                ]
            ),
            "name": context.get(
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
            "manifest_type": "field",
            "storage_layout_version":
                STORAGE_LAYOUT_VERSION,
            "user_id": str(
                context[
                    "user_id"
                ]
            ),
            "farm_id": str(
                context[
                    "farm_id"
                ]
            ),
            "field_id": str(
                context[
                    "field_id"
                ]
            ),
            "name": context.get(
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
    observation_query = text(
        """
        SELECT
            id,
            field_id,
            observed_on,
            source,
            scene_id,
            cloud_cover_percent,
            valid_pixel_percent,
            resolution_m,
            pixel_count,
            valid_pixel_count,
            metadata_json,
            created_at,
            updated_at

        FROM satellite_observations

        WHERE id = :observation_id
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

        ORDER BY metric_type
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
            ST_AsGeoJSON(geometry)
                AS geometry,
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

    metrics_payload = {}

    for row in metrics:
        metric_type = str(
            row["metric_type"]
        )

        metrics_payload[
            metric_type
        ] = {
            "file":
                f"{metric_type}.tif",
            "raster_uri":
                row["raster_uri"],
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
                row["pixel_count"],
            "valid_pixel_count":
                row[
                    "valid_pixel_count"
                ],
            "valid_pixel_percent":
                row[
                    "valid_pixel_percent"
                ],
            "metadata":
                row["metadata_json"],
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
                    str(row["id"]),
                "metric_type":
                    row["index_type"],
                "zone_index":
                    row["zone_index"],
                "anomaly_type":
                    row["anomaly_type"],
                "severity":
                    row["severity"],
                "geometry":
                    geometry,
                "pixel_count":
                    row["pixel_count"],
                "area_sqm":
                    row["area_sqm"],
                "area_acres":
                    row["area_acres"],
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
                    row["metadata_json"],
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
            "valid_pixel_percent":
                observation[
                    "valid_pixel_percent"
                ],
            "resolution_m":
                observation[
                    "resolution_m"
                ],
            "pixel_count":
                observation[
                    "pixel_count"
                ],
            "valid_pixel_count":
                observation[
                    "valid_pixel_count"
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
def write_media_manifest_from_database(
    *,
    media_id: UUID,
) -> None:
    query = text(
        """
        SELECT
            ma.id AS media_id,
            ma.uploaded_by_user_id AS user_id,
            ma.field_id,
            ma.activity_id,
            ma.crop_cycle_id,
            ma.media_type,
            ma.status,
            ma.bucket_name,
            ma.object_key,
            ma.thumbnail_object_key,
            ma.original_filename,
            ma.content_type,
            ma.size_bytes,
            ma.captured_at,
            ma.width,
            ma.height,
            ma.duration_seconds,
            ma.caption,
            ma.metadata_json,
            ma.created_at,
            ma.updated_at,

            u.name AS user_name,
            u.phone_e164,
            u.preferred_language,

            fa.id AS farm_id,
            fa.name AS farm_name,
            fa.storage_slug AS farm_storage_slug,
            fa.location_name AS farm_location_name,
            fa.created_at AS farm_created_at,
            fa.updated_at AS farm_updated_at,

            f.name AS field_name,
            f.storage_slug AS field_storage_slug,
            f.created_at AS field_created_at,
            f.updated_at AS field_updated_at,
            ST_AsGeoJSON(f.boundary) AS field_boundary,

            a.activity_type,
            a.occurred_at AS activity_occurred_at,
            a.notes AS activity_notes,
            a.details AS activity_details,

            cc.season_id,
            cc.crop_name,
            cc.variety,
            cc.status AS crop_status,
            cc.started_on AS crop_started_on,
            cc.planted_on,
            cc.expected_harvest_on,
            cc.harvested_on,
            cc.yield_kg,
            cc.harvested_area_acres,
            cc.moisture_percent,
            cc.quality_grade,
            cc.selling_price_per_kg,
            cc.harvest_notes

        FROM media_assets AS ma

        JOIN users AS u
            ON u.id = ma.uploaded_by_user_id

        JOIN fields AS f
            ON f.id = ma.field_id

        JOIN farms AS fa
            ON fa.id = f.farm_id

        LEFT JOIN activities AS a
            ON a.id = ma.activity_id

        LEFT JOIN crop_cycles AS cc
            ON cc.id = ma.crop_cycle_id

        WHERE ma.id = :media_id
        """
    )

    with engine.connect() as connection:
        row = (
            connection.execute(
                query,
                {
                    "media_id":
                        media_id,
                },
            )
            .mappings()
            .first()
        )

    if row is None:
        raise RuntimeError(
            f"Media {media_id} not found."
        )

    row = dict(row)

    boundary = row[
        "field_boundary"
    ]

    if isinstance(
        boundary,
        str,
    ):
        boundary = json.loads(
            boundary
        )

    context = {
        "user_id":
            row["user_id"],
        "user_name":
            row["user_name"],
        "phone_e164":
            row["phone_e164"],
        "preferred_language":
            row["preferred_language"],
        "farm_id":
            row["farm_id"],
        "farm_name":
            row["farm_name"],
        "farm_storage_slug":
            row["farm_storage_slug"],
        "farm_location_name":
            row["farm_location_name"],
        "farm_created_at":
            row["farm_created_at"],
        "farm_updated_at":
            row["farm_updated_at"],
        "field_id":
            row["field_id"],
        "field_name":
            row["field_name"],
        "field_storage_slug":
            row["field_storage_slug"],
        "field_boundary":
            boundary,
        "field_created_at":
            row["field_created_at"],
        "field_updated_at":
            row["field_updated_at"],
    }

    write_hierarchy_manifests(
        context
    )

    metadata = (
        row["metadata_json"]
        or {}
    )

    storage_date = None

    raw_storage_date = metadata.get(
        "storage_date"
    )

    if isinstance(
        raw_storage_date,
        str,
    ):
        try:
            storage_date = date.fromisoformat(
                raw_storage_date
            )
        except ValueError:
            storage_date = None

    if storage_date is None:
        if row["captured_at"] is not None:
            storage_date = row[
                "captured_at"
            ].date()
        else:
            storage_date = row[
                "created_at"
            ].date()

    files = {
        "original": {
            "object_key":
                row["object_key"],
            "uri":
                f"gs://{row['bucket_name']}/{row['object_key']}",
            "content_type":
                row["content_type"],
            "size_bytes":
                row["size_bytes"],
        }
    }

    if row[
        "thumbnail_object_key"
    ]:
        files[
            "preview"
        ] = {
            "object_key":
                row[
                    "thumbnail_object_key"
                ],
            "uri":
                f"gs://{row['bucket_name']}/{row['thumbnail_object_key']}",
        }

    activity = None

    if row["activity_id"]:
        activity = {
            "activity_id":
                str(row["activity_id"]),
            "activity_type":
                row["activity_type"],
            "occurred_at":
                row[
                    "activity_occurred_at"
                ],
            "notes":
                row["activity_notes"],
            "details":
                row["activity_details"],
        }

    crop_cycle = None

    if row["crop_cycle_id"]:
        crop_cycle = {
            "crop_cycle_id":
                str(
                    row["crop_cycle_id"]
                ),
            "season_id":
                str(row["season_id"])
                if row["season_id"]
                else None,
            "crop_name":
                row["crop_name"],
            "variety":
                row["variety"],
            "status":
                row["crop_status"],
            "started_on":
                row["crop_started_on"],
            "planted_on":
                row["planted_on"],
            "expected_harvest_on":
                row[
                    "expected_harvest_on"
                ],
            "harvested_on":
                row["harvested_on"],
            "yield_kg":
                row["yield_kg"],
            "harvested_area_acres":
                row[
                    "harvested_area_acres"
                ],
            "moisture_percent":
                row["moisture_percent"],
            "quality_grade":
                row["quality_grade"],
            "selling_price_per_kg":
                row[
                    "selling_price_per_kg"
                ],
            "harvest_notes":
                row["harvest_notes"],
        }

    manifest_key = (
        f"{row['object_key'].rsplit('/', 1)[0]}"
        "/manifest.json"
    )

    _write_json(
        object_key=manifest_key,
        payload={
            "manifest_type":
                "media_asset",
            "storage_layout_version":
                STORAGE_LAYOUT_VERSION,
            "media_id":
                str(row["media_id"]),
            "user_id":
                str(row["user_id"]),
            "farm_id":
                str(row["farm_id"]),
            "field_id":
                str(row["field_id"]),
            "activity_id":
                str(row["activity_id"])
                if row["activity_id"]
                else None,
            "crop_cycle_id":
                str(row["crop_cycle_id"])
                if row["crop_cycle_id"]
                else None,
            "storage_date":
                storage_date,
            "media_type":
                row["media_type"],
            "status":
                row["status"],
            "original_filename":
                row["original_filename"],
            "content_type":
                row["content_type"],
            "size_bytes":
                row["size_bytes"],
            "captured_at":
                row["captured_at"],
            "width":
                row["width"],
            "height":
                row["height"],
            "duration_seconds":
                row["duration_seconds"],
            "caption":
                row["caption"],
            "activity":
                activity,
            "crop_cycle":
                crop_cycle,
            "files":
                files,
            "metadata":
                metadata,
            "created_at":
                row["created_at"],
            "updated_at":
                row["updated_at"],
            "manifest_generated_at":
                datetime.now(
                    timezone.utc
                ),
        },
    )
