
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)


MediaType = Literal[
    "image",
    "video",
]

MediaStatus = Literal[
    "pending",
    "ready",
    "failed",
]

MediaUploadMethod = Literal[
    "api_put",
    "gcs_signed_put",
]


class MediaUploadCreate(BaseModel):
    original_filename: str = Field(
        min_length=1,
        max_length=255,
    )

    content_type: str = Field(
        min_length=1,
        max_length=120,
    )

    size_bytes: int = Field(
        gt=0,
    )

    activity_id: UUID | None = None

    crop_cycle_id: UUID | None = None

    captured_at: datetime | None = None

    caption: str | None = Field(
        default=None,
        max_length=1000,
    )

    @field_validator("captured_at")
    @classmethod
    def require_timezone(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "captured_at must include a timezone."
            )

        return value


class MediaAssetResponse(BaseModel):
    id: UUID

    uploaded_by_user_id: UUID

    field_id: UUID

    activity_id: UUID | None

    crop_cycle_id: UUID | None

    media_type: MediaType

    status: MediaStatus

    storage_backend: str

    original_filename: str

    content_type: str

    size_bytes: int

    captured_at: datetime | None

    width: int | None

    height: int | None

    duration_seconds: float | None

    caption: str | None

    metadata_json: dict

    download_url: str | None

    thumbnail_available: bool

    thumbnail_url: str | None

    created_at: datetime

    updated_at: datetime


class MediaUploadTarget(BaseModel):
    media: MediaAssetResponse

    upload_method: MediaUploadMethod

    upload_url: str

    upload_headers: dict[str, str]
