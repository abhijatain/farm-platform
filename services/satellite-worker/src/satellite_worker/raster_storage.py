
from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

from satellite_worker.gcs_client import (
    gcs_bucket,
    gcs_client,
)
from satellite_worker.storage_layout import (
    satellite_metric_key,
)


def publish_metric_rasters(
    *,
    context: dict,
    observed_on,
    observation_id: UUID,
    results: list,
) -> dict[str, str]:
    """
    Upload all generated metric COGs to their final private GCS keys.

    The worker never stores file:// paths in PostgreSQL.
    """

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
                str(source_path),
                content_type="image/tiff",
            )

            blob.reload(
                client=gcs_client()
            )

            local_size = (
                source_path
                .stat()
                .st_size
            )

            remote_size = int(
                blob.size or 0
            )

            if local_size != remote_size:
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
