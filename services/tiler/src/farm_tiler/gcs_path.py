
from __future__ import annotations

from datetime import timedelta
from functools import lru_cache
from urllib.parse import urlparse

from fastapi import (
    HTTPException,
    Query,
)
from google.cloud import storage

from farm_tiler.config import settings


@lru_cache(maxsize=1)
def _client() -> storage.Client:
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


def _signed_gcs_get_url(
    gs_uri: str,
) -> str:
    parsed = urlparse(
        gs_uri
    )

    if (
        parsed.scheme != "gs"
        or not parsed.netloc
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Only private gs:// raster URIs "
                "are supported."
            ),
        )

    bucket_name = (
        parsed.netloc
    )

    object_key = (
        parsed.path
        .lstrip("/")
    )

    if not object_key:
        raise HTTPException(
            status_code=400,
            detail=(
                "GCS raster object key is missing."
            ),
        )

    if (
        bucket_name
        != settings.gcs_bucket_name
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "This GCS bucket is not "
                "allowed by the tiler."
            ),
        )

    # The current canonical object layout starts at users/.
    # Rejecting old/arbitrary paths prevents the tiler from becoming a
    # generic authenticated GCS proxy.
    if not object_key.startswith(
        "users/"
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Raster is outside the canonical "
                "Farm Platform storage layout."
            ),
        )

    blob = (
        _client()
        .bucket(
            bucket_name
        )
        .blob(
            object_key
        )
    )

    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(
            minutes=(
                settings
                .gcs_read_url_expiry_minutes
            )
        ),
        method="GET",
    )


def DatasetPathParams(
    url: str = Query(
        ...,
        description=(
            "Private Farm Platform gs:// COG URI."
        ),
    ),
) -> str:
    return _signed_gcs_get_url(
        url
    )
