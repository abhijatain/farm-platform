"""Enforce media upload policy and build secure media object responses.

Reusable size/MIME checks, signed access and manifest handling are shared
across HTTP routes without coupling to FastAPI dependency-injection aliases.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.media_asset import MediaAsset
from app.models.user import User
from app.schemas.media import MediaAssetResponse
from app.domains.media.processing import process_media_asset
from app.services.ownership import get_owned_field
from app.storage import get_storage
from app.storage.manifests import write_media_manifests


ContentTypeInfo = tuple[
    Literal[
        "image",
        "video",
    ],
    str,
]


ALLOWED_CONTENT_TYPES: dict[
    str,
    ContentTypeInfo,
] = {
    "image/jpeg": (
        "image",
        ".jpg",
    ),
    "image/png": (
        "image",
        ".png",
    ),
    "image/webp": (
        "image",
        ".webp",
    ),
    "image/heic": (
        "image",
        ".heic",
    ),
    "image/heif": (
        "image",
        ".heif",
    ),
    "video/mp4": (
        "video",
        ".mp4",
    ),
    "video/quicktime": (
        "video",
        ".mov",
    ),
    "video/webm": (
        "video",
        ".webm",
    ),
}


def _normalized_content_type(
    value: str,
) -> str:
    return (
        value
        .split(
            ";",
            maxsplit=1,
        )[0]
        .strip()
        .lower()
    )


def _media_type_info(
    content_type: str,
) -> ContentTypeInfo:
    normalized = _normalized_content_type(
        content_type
    )

    info = ALLOWED_CONTENT_TYPES.get(
        normalized
    )

    if info is None:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_CONTENT
            ),
            detail=(
                "Unsupported media type. "
                "Supported images: JPEG, PNG, WebP, HEIC/HEIF. "
                "Supported videos: MP4, MOV, WebM."
            ),
        )

    return info


def _maximum_size(
    media_type: str,
) -> int:
    if media_type == "image":
        return settings.media_max_image_bytes

    return settings.media_max_video_bytes


def _validate_size(
    *,
    media_type: str,
    size_bytes: int,
) -> None:
    maximum = _maximum_size(
        media_type
    )

    if size_bytes > maximum:
        maximum_mb = (
            maximum
            / 1024
            / 1024
        )

        raise HTTPException(
            status_code=(
                status.HTTP_413_CONTENT_TOO_LARGE
            ),
            detail=(
                f"{media_type.capitalize()} is too large. "
                f"Maximum size is {maximum_mb:.0f} MB."
            ),
        )


def _get_owned_media(
    *,
    media_id: UUID,
    db: Session,
    current_user: User,
) -> MediaAsset:
    media = db.scalar(
        select(MediaAsset).where(
            MediaAsset.id
            == media_id
        )
    )

    if media is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Media not found.",
        )

    get_owned_field(
        db=db,
        user_id=current_user.id,
        field_id=media.field_id,
    )

    return media


def _signed_download_url(
    object_key: str | None,
) -> str | None:
    if not object_key:
        return None

    return (
        get_storage()
        .create_signed_download_url(
            object_key=object_key,
            expires_minutes=(
                settings
                .media_download_url_expiry_minutes
            ),
        )
    )


def _to_response(
    media: MediaAsset,
) -> MediaAssetResponse:
    return MediaAssetResponse(
        id=media.id,
        uploaded_by_user_id=(
            media.uploaded_by_user_id
        ),
        field_id=media.field_id,
        activity_id=media.activity_id,
        crop_cycle_id=(
            media.crop_cycle_id
        ),
        media_type=media.media_type,
        status=media.status,
        original_filename=(
            media.original_filename
        ),
        content_type=(
            media.content_type
        ),
        size_bytes=media.size_bytes,
        captured_at=(
            media.captured_at
        ),
        width=media.width,
        height=media.height,
        duration_seconds=(
            media.duration_seconds
        ),
        caption=media.caption,
        metadata_json=(
            media.metadata_json
        ),
        download_url=(
            _signed_download_url(
                media.object_key
            )
            if media.status == "ready"
            else None
        ),
        preview_url=(
            _signed_download_url(
                media.preview_object_key
            )
            if media.status == "ready"
            else None
        ),
        created_at=(
            media.created_at
        ),
        updated_at=(
            media.updated_at
        ),
    )


def _queue_derivative_processing(
    *,
    media: MediaAsset,
    background_tasks: BackgroundTasks,
) -> None:
    if not (
        settings
        .media_derivatives_enabled
    ):
        return

    current_metadata = (
        media.metadata_json
        or {}
    )

    if (
        current_metadata.get(
            "derivative_status"
        )
        == "complete"
        and media.preview_object_key
    ):
        return

    media.metadata_json = {
        **current_metadata,
        "derivative_status": "queued",
        "derivative_error": None,
    }

    background_tasks.add_task(
        process_media_asset,
        media.id,
    )


def _write_manifests_best_effort(
    *,
    db: Session,
    media: MediaAsset,
) -> None:
    # Cloud recovery manifests are best-effort; the canonical database commit
    # must not fail solely because a manifest refresh was unavailable.
    try:
        write_media_manifests(
            db=db,
            media=media,
        )
    except Exception as error:
        print(
            "Media manifest write failed: "
            f"{type(error).__name__}: "
            f"{error}"
        )


