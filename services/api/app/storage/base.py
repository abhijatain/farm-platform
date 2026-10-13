
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StorageObjectInfo:
    size_bytes: int
    content_type: str | None
    etag: str | None = None


class StorageBackend(ABC):
    backend_name: str

    @property
    @abstractmethod
    def bucket_name(self) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def object_uri(
        self,
        object_key: str,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def exists(
        self,
        object_key: str,
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    def stat(
        self,
        object_key: str,
    ) -> StorageObjectInfo | None:
        raise NotImplementedError

    @abstractmethod
    def delete(
        self,
        object_key: str,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def create_signed_upload_url(
        self,
        *,
        object_key: str,
        content_type: str,
        expires_minutes: int,
    ) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def create_signed_download_url(
        self,
        *,
        object_key: str,
        expires_minutes: int,
    ) -> str | None:
        raise NotImplementedError

    async def put_async_chunks(
        self,
        *,
        object_key: str,
        chunks: AsyncIterable[bytes],
        content_type: str,
        expected_size: int,
        max_size: int,
    ) -> StorageObjectInfo:
        raise RuntimeError(
            f"{self.backend_name} does not support API-streamed uploads."
        )

    def local_path(
        self,
        object_key: str,
    ) -> Path | None:
        return None
