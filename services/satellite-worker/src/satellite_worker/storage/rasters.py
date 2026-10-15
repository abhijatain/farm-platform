"""Publish canonical metric COG files and return permanent GCS URIs."""

from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID, uuid4

from satellite_worker.storage.gcs import (
    gcs_bucket,
    gcs_client,
)
from satellite_worker.storage.layout import (
    satellite_metric_key,
)


def _delete_quietly(
    *,
    bucket,
    object_key: str,
    client,
) -> None:
    try:
        bucket.blob(
            object_key
        ).delete(
            client=client
        )
    except Exception:
        pass


def publish_metric_rasters(
    *,
    context: dict,
    observed_on,
    observation_id: UUID,
    results: list,
) -> dict[str, str]:
    """
    Publish metric COGs without corrupting an existing observation on reruns.

    Every result is first uploaded and verified under a temporary staging key.
    Existing canonical objects are backed up before promotion. If promotion
    fails, already-promoted keys are restored to their previous content.
    """

    bucket = gcs_bucket()
    client = gcs_client()
    run_id = uuid4().hex

    staged: list[
        tuple[
            str,
            Path,
            str,
            str,
        ]
    ] = []

    backup_keys: dict[
        str,
        str | None,
    ] = {}

    promoted_keys: list[str] = []
    raster_uris: dict[str, str] = {}

    try:
        # Stage and verify every generated raster before touching a canonical
        # object. Upload/verification failures leave the old run intact.
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

            final_key = (
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

            staging_key = (
                f"{final_key}.staging-"
                f"{run_id}"
            )

            staging_blob = bucket.blob(
                staging_key
            )

            staging_blob.upload_from_filename(
                str(source_path),
                content_type="image/tiff",
            )

            staging_blob.reload(
                client=client
            )

            local_size = (
                source_path
                .stat()
                .st_size
            )

            remote_size = int(
                staging_blob.size
                or 0
            )

            if local_size != remote_size:
                raise RuntimeError(
                    "Staged COG size mismatch "
                    f"for {metric_type}: "
                    f"local={local_size}, "
                    f"gcs={remote_size}"
                )

            staged.append(
                (
                    metric_type,
                    source_path,
                    final_key,
                    staging_key,
                )
            )

        # Snapshot existing canonical objects before any overwrite.
        for (
            _,
            _,
            final_key,
            _,
        ) in staged:
            final_blob = bucket.blob(
                final_key
            )

            if final_blob.exists(
                client=client
            ):
                backup_key = (
                    f"{final_key}.backup-"
                    f"{run_id}"
                )

                bucket.copy_blob(
                    final_blob,
                    bucket,
                    new_name=(
                        backup_key
                    ),
                    client=client,
                )

                backup_keys[
                    final_key
                ] = backup_key

            else:
                backup_keys[
                    final_key
                ] = None

        # Promote staged objects only after every stage/backup succeeded.
        for (
            metric_type,
            source_path,
            final_key,
            staging_key,
        ) in staged:
            staging_blob = bucket.blob(
                staging_key
            )

            bucket.copy_blob(
                staging_blob,
                bucket,
                new_name=final_key,
                client=client,
            )

            # Record immediately so verification failures are also rolled back.
            promoted_keys.append(
                final_key
            )

            final_blob = bucket.blob(
                final_key
            )

            final_blob.reload(
                client=client
            )

            expected_size = (
                source_path
                .stat()
                .st_size
            )

            final_size = int(
                final_blob.size
                or 0
            )

            if expected_size != final_size:
                raise RuntimeError(
                    "Published COG size mismatch "
                    f"for {metric_type}: "
                    f"local={expected_size}, "
                    f"gcs={final_size}"
                )

            raster_uris[
                metric_type
            ] = (
                f"gs://{bucket.name}/"
                f"{final_key}"
            )

            print(
                "  Uploaded "
                f"{metric_type.upper()} "
                f"→ {raster_uris[metric_type]}"
            )

    except Exception:
        for final_key in reversed(
            promoted_keys
        ):
            backup_key = (
                backup_keys.get(
                    final_key
                )
            )

            try:
                if backup_key:
                    bucket.copy_blob(
                        bucket.blob(
                            backup_key
                        ),
                        bucket,
                        new_name=(
                            final_key
                        ),
                        client=client,
                    )
                else:
                    bucket.blob(
                        final_key
                    ).delete(
                        client=client
                    )
            except Exception:
                # Preserve the original error. Storage reconciliation can
                # detect a rare rollback failure later.
                pass

        raise

    finally:
        for (
            _,
            _,
            _,
            staging_key,
        ) in staged:
            _delete_quietly(
                bucket=bucket,
                object_key=(
                    staging_key
                ),
                client=client,
            )

        for backup_key in (
            backup_keys.values()
        ):
            if backup_key:
                _delete_quietly(
                    bucket=bucket,
                    object_key=(
                        backup_key
                    ),
                    client=client,
                )

    return raster_uris


def _parse_gs_uri(
    raster_uri: str,
) -> tuple[str, str]:
    parsed = urlparse(
        raster_uri
    )

    if (
        parsed.scheme != "gs"
        or not parsed.netloc
        or not parsed.path
    ):
        raise ValueError(
            "Expected canonical gs:// raster URI. "
            f"Received: {raster_uri}"
        )

    return (
        parsed.netloc,
        parsed.path.lstrip("/"),
    )


@contextmanager
def materialize_metric_raster(
    raster_uri: str,
):
    """
    Download a GCS COG to an ephemeral temporary file for algorithms that
    require a local rasterio path. The file is always removed afterwards.
    """

    bucket_name, object_key = (
        _parse_gs_uri(
            raster_uri
        )
    )

    with tempfile.TemporaryDirectory(
        prefix="farm-raster-"
    ) as temporary:
        destination = (
            Path(temporary)
            / Path(object_key).name
        )

        (
            gcs_client()
            .bucket(
                bucket_name
            )
            .blob(
                object_key
            )
            .download_to_filename(
                str(destination)
            )
        )

        yield destination
