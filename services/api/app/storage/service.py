"""Provide configured cloud object storage for API endpoints."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.storage.gcs import GCSStorage


@lru_cache(maxsize=1)
def get_storage() -> GCSStorage:
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
