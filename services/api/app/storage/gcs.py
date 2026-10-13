
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from google.cloud import storage

from app.storage.base import StorageBackend, StorageObjectInfo


class GCSStorage(StorageBackend):
    backend_name = "gcs"

    def __init__(
        self,
        *,
        bucket_name: str,
        project_id: str | None = None,
        credentials_path: Path | None = None,
    ) -> None:
        if credentials_path is not None:
            self.client = (
                storage.Client.from_service_account_json(
                    str(credentials_path),
                    project=project_id,
                )
            )
        else:
            self.client = storage.Client(
                project=project_id,
            )

        self._bucket_name = bucket_name

        self.bucket = self.client.bucket(
            bucket_name
        )

    @property
    def bucket_name(self) -> str:
        return self._bucket_name

    def _blob(
        self,
        object_key: str,
    ):
        return self.bucket.blob(
            object_key.lstrip("/")
        )

    def object_uri(
        self,
        object_key: str,
    ) -> str:
        return (
            f"gs://{self._bucket_name}/"
            f"{object_key.lstrip('/')}"
        )

    def exists(
        self,
        object_key: str,
    ) -> bool:
        return self._blob(
            object_key
        ).exists(
            self.client
        )

    def stat(
        self,
        object_key: str,
    ) -> StorageObjectInfo | None:
        blob = self._blob(
            object_key
        )

        if not blob.exists(
            self.client
        ):
            return None

        blob.reload(
            client=self.client
        )

        return StorageObjectInfo(
            size_bytes=int(
                blob.size or 0
            ),
            content_type=blob.content_type,
            etag=blob.etag,
        )

    def delete(
        self,
        object_key: str,
    ) -> None:
        blob = self._blob(
            object_key
        )

        if blob.exists(
            self.client
        ):
            blob.delete(
                client=self.client
            )

    def create_signed_upload_url(
        self,
        *,
        object_key: str,
        content_type: str,
        expires_minutes: int,
    ) -> str:
        return self._blob(
            object_key
        ).generate_signed_url(
            version="v4",
            expiration=timedelta(
                minutes=expires_minutes
            ),
            method="PUT",
            content_type=content_type,
        )

    def create_signed_download_url(
        self,
        *,
        object_key: str,
        expires_minutes: int,
    ) -> str:
        return self._blob(
            object_key
        ).generate_signed_url(
            version="v4",
            expiration=timedelta(
                minutes=expires_minutes
            ),
            method="GET",
        )
