
from __future__ import annotations

from functools import lru_cache

from google.cloud import storage

from satellite_worker.config import settings


@lru_cache(maxsize=1)
def gcs_client() -> storage.Client:
    if (
        settings
        .gcs_credentials_path
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


@lru_cache(maxsize=4)
def gcs_bucket(
    bucket_name: str | None = None,
):
    resolved = (
        bucket_name
        or settings.gcs_bucket_name
    )

    if not resolved:
        raise RuntimeError(
            "GCS_BUCKET_NAME is required."
        )

    return gcs_client().bucket(
        resolved
    )
