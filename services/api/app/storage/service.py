
from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.storage.base import StorageBackend
from app.storage.gcs import GCSStorage
from app.storage.local import LocalStorage


@lru_cache(maxsize=1)
def _local_storage() -> LocalStorage:
    return LocalStorage(
        settings.storage_local_root
    )


@lru_cache(maxsize=16)
def _gcs_storage(
    bucket_name: str,
) -> GCSStorage:
    return GCSStorage(
        bucket_name=bucket_name,
        project_id=(
            settings.gcs_project_id
        ),
        credentials_path=(
            settings.gcs_credentials_path
        ),
    )


def get_storage_for_location(
    *,
    storage_backend: str,
    bucket_name: str | None = None,
) -> StorageBackend:
    backend = (
        storage_backend
        .strip()
        .lower()
    )

    if backend == "local":
        return _local_storage()

    if backend == "gcs":
        resolved_bucket = (
            bucket_name
            or settings.gcs_bucket_name
        )

        if not resolved_bucket:
            raise RuntimeError(
                "A GCS bucket name is required "
                "for GCS-backed storage."
            )

        return _gcs_storage(
            resolved_bucket
        )

    raise RuntimeError(
        "Unsupported storage backend: "
        f"{storage_backend}"
    )


def get_storage() -> StorageBackend:
    return get_storage_for_location(
        storage_backend=(
            settings.storage_backend
        ),
        bucket_name=(
            settings.gcs_bucket_name
        ),
    )
