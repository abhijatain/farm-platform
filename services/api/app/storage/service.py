
from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.storage.base import StorageBackend
from app.storage.gcs import GCSStorage
from app.storage.local import LocalStorage


@lru_cache(maxsize=1)
def get_storage() -> StorageBackend:
    backend = (
        settings.storage_backend
        .strip()
        .lower()
    )

    if backend == "local":
        return LocalStorage(
            settings.storage_local_root
        )

    if backend == "gcs":
        if not settings.gcs_bucket_name:
            raise RuntimeError(
                "GCS_BUCKET_NAME is required "
                "when STORAGE_BACKEND=gcs."
            )

        return GCSStorage(
            bucket_name=(
                settings.gcs_bucket_name
            ),
            project_id=(
                settings.gcs_project_id
            ),
            credentials_path=(
                settings.gcs_credentials_path
            ),
        )

    raise RuntimeError(
        "Unsupported STORAGE_BACKEND: "
        f"{settings.storage_backend}"
    )
