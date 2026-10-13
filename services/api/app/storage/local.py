
from __future__ import annotations

import mimetypes
from collections.abc import AsyncIterable
from pathlib import Path

from app.storage.base import StorageBackend, StorageObjectInfo


class LocalStorage(StorageBackend):
    backend_name = "local"

    def __init__(
        self,
        root: Path,
    ) -> None:
        self.root = root.resolve()

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

    @property
    def bucket_name(self) -> str | None:
        return None

    def _path(
        self,
        object_key: str,
    ) -> Path:
        normalized = object_key.lstrip("/")

        path = (
            self.root / normalized
        ).resolve()

        if (
            path != self.root
            and self.root not in path.parents
        ):
            raise ValueError(
                "Invalid storage object key."
            )

        return path

    def object_uri(
        self,
        object_key: str,
    ) -> str:
        return (
            self._path(object_key)
            .resolve()
            .as_uri()
        )

    def exists(
        self,
        object_key: str,
    ) -> bool:
        return self._path(
            object_key
        ).is_file()

    def stat(
        self,
        object_key: str,
    ) -> StorageObjectInfo | None:
        path = self._path(
            object_key
        )

        if not path.is_file():
            return None

        content_type, _ = (
            mimetypes.guess_type(
                path.name
            )
        )

        return StorageObjectInfo(
            size_bytes=path.stat().st_size,
            content_type=content_type,
            etag=None,
        )

    def delete(
        self,
        object_key: str,
    ) -> None:
        path = self._path(
            object_key
        )

        path.unlink(
            missing_ok=True
        )

        parent = path.parent

        while parent != self.root:
            try:
                parent.rmdir()
            except OSError:
                break

            parent = parent.parent

    def create_signed_upload_url(
        self,
        *,
        object_key: str,
        content_type: str,
        expires_minutes: int,
    ) -> str | None:
        return None

    def create_signed_download_url(
        self,
        *,
        object_key: str,
        expires_minutes: int,
    ) -> str | None:
        return None

    async def put_async_chunks(
        self,
        *,
        object_key: str,
        chunks: AsyncIterable[bytes],
        content_type: str,
        expected_size: int,
        max_size: int,
    ) -> StorageObjectInfo:
        path = self._path(
            object_key
        )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = (
            path.with_name(
                f".{path.name}.part"
            )
        )

        total = 0

        try:
            with temporary_path.open(
                "wb"
            ) as file_handle:
                async for chunk in chunks:
                    if not chunk:
                        continue

                    total += len(chunk)

                    if total > max_size:
                        raise ValueError(
                            "Uploaded file exceeds "
                            "the allowed size."
                        )

                    file_handle.write(
                        chunk
                    )

            if total != expected_size:
                raise ValueError(
                    "Uploaded file size did not "
                    "match the declared size."
                )

            temporary_path.replace(
                path
            )

        except Exception:
            temporary_path.unlink(
                missing_ok=True
            )

            raise

        return StorageObjectInfo(
            size_bytes=total,
            content_type=content_type,
            etag=None,
        )

    def local_path(
        self,
        object_key: str,
    ) -> Path | None:
        path = self._path(
            object_key
        )

        return (
            path
            if path.is_file()
            else None
        )
