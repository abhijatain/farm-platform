
from __future__ import annotations

from pathlib import Path
from uuid import UUID

from sqlalchemy import text

from satellite_worker.config import settings
from satellite_worker.db import engine
from satellite_worker.gcs_client import (
    gcs_bucket,
    gcs_client,
)
from satellite_worker.storage_layout import (
    STORAGE_LAYOUT_VERSION,
    satellite_metric_key,
)


def _normalized_backend() -> str:
    return (
        settings
        .satellite_storage_backend
        .strip()
        .lower()
    )


def publish_metric_rasters(
    *,
    context: dict,
    observed_on,
    observation_id: UUID,
    results: list,
) -> dict[str, str]:
    backend = _normalized_backend()

    if backend == "local":
        return {
            result.metric_type:
                result.raster_path
                .resolve()
                .as_uri()
            for result in results
        }

    if backend != "gcs":
        raise RuntimeError(
            "Unsupported SATELLITE_STORAGE_BACKEND: "
            f"{settings.satellite_storage_backend}"
        )

    bucket = gcs_bucket()

    uploaded_keys: list[str] = []
    raster_uris: dict[str, str] = {}

    try:
        for result in results:
            metric_type = (
                result.metric_type
                .strip()
                .lower()
            )

            source_path = (
                result.raster_path
                .resolve()
            )

            if not source_path.is_file():
                raise FileNotFoundError(
                    "Metric COG not found: "
                    f"{source_path}"
                )

            object_key = satellite_metric_key(
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

            blob = bucket.blob(
                object_key
            )

            blob.upload_from_filename(
                str(source_path),
                content_type="image/tiff",
            )

            blob.reload(
                client=gcs_client()
            )

            remote_size = int(
                blob.size or 0
            )

            local_size = (
                source_path
                .stat()
                .st_size
            )

            if remote_size != local_size:
                raise RuntimeError(
                    "Uploaded COG size mismatch "
                    f"for {metric_type}: "
                    f"local={local_size}, "
                    f"gcs={remote_size}"
                )

            uploaded_keys.append(
                object_key
            )

            raster_uris[
                metric_type
            ] = (
                f"gs://{bucket.name}/"
                f"{object_key}"
            )

            print(
                "  Uploaded "
                f"{metric_type.upper()} "
                f"→ {raster_uris[metric_type]}"
            )

    except Exception:
        for object_key in uploaded_keys:
            try:
                bucket.blob(
                    object_key
                ).delete(
                    client=gcs_client()
                )
            except Exception:
                pass

        raise

    return raster_uris


def update_satellite_raster_uris(
    *,
    observation_id: UUID,
    raster_uris: dict[
        str,
        str,
    ],
) -> None:
    backend = _normalized_backend()

    bucket_name = (
        settings.gcs_bucket_name
        if backend == "gcs"
        else None
    )

    metric_query = text(
        """
        UPDATE satellite_metrics

        SET
            raster_uri =
                :raster_uri,

            metadata_json =
                COALESCE(
                    metadata_json,
                    '{}'::jsonb
                )
                ||
                jsonb_build_object(
                    'storage_backend',
                    CAST(
                        :storage_backend
                        AS text
                    ),
                    'storage_bucket',
                    CAST(
                        :storage_bucket
                        AS text
                    ),
                    'storage_layout_version',
                    CAST(
                        :storage_layout_version
                        AS integer
                    )
                ),

            updated_at =
                NOW()

        WHERE
            satellite_observation_id =
                :observation_id

        AND metric_type =
                :metric_type
        """
    )

    observation_query = text(
        """
        UPDATE satellite_observations

        SET
            ndvi_raster_uri =
                COALESCE(
                    :ndvi_raster_uri,
                    ndvi_raster_uri
                ),

            metadata_json =
                COALESCE(
                    metadata_json,
                    '{}'::jsonb
                )
                ||
                jsonb_build_object(
                    'raster_storage',
                    jsonb_build_object(
                        'backend',
                        CAST(
                            :storage_backend
                            AS text
                        ),
                        'bucket',
                        CAST(
                            :storage_bucket
                            AS text
                        ),
                        'layout_version',
                        CAST(
                            :storage_layout_version
                            AS integer
                        )
                    )
                ),

            updated_at =
                NOW()

        WHERE id =
            :observation_id
        """
    )

    with engine.begin() as connection:
        for (
            metric_type,
            raster_uri,
        ) in raster_uris.items():
            connection.execute(
                metric_query,
                {
                    "observation_id":
                        observation_id,
                    "metric_type":
                        metric_type,
                    "raster_uri":
                        raster_uri,
                    "storage_backend":
                        backend,
                    "storage_bucket":
                        bucket_name,
                    "storage_layout_version":
                        STORAGE_LAYOUT_VERSION,
                },
            )

        connection.execute(
            observation_query,
            {
                "observation_id":
                    observation_id,
                "ndvi_raster_uri":
                    raster_uris.get(
                        "ndvi"
                    ),
                "storage_backend":
                    backend,
                "storage_bucket":
                    bucket_name,
                "storage_layout_version":
                    STORAGE_LAYOUT_VERSION,
            },
        )


def remove_local_metric_rasters(
    results: list,
) -> None:
    if not (
        settings
        .satellite_delete_local_after_upload
    ):
        return

    if (
        _normalized_backend()
        != "gcs"
    ):
        return

    directories: set[Path] = set()

    for result in results:
        path = (
            result.raster_path
            .resolve()
        )

        directories.add(
            path.parent
        )

        try:
            path.unlink(
                missing_ok=True
            )
        except OSError as error:
            print(
                "  Warning: unable to remove local COG "
                f"{path}: {error}"
            )

    for directory in sorted(
        directories,
        key=lambda value:
            len(value.parts),
        reverse=True,
    ):
        current = directory

        for _ in range(2):
            try:
                current.rmdir()
            except OSError:
                break

            current = current.parent
