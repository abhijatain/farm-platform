
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    Query,
    Response,
    status,
)
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession
from app.core.config import settings
from app.models.activity import Activity
from app.models.farm import Farm
from app.models.media_asset import MediaAsset
from app.schemas.media import (
    MediaAssetResponse,
    MediaUploadCreate,
    MediaUploadTarget,
)
from app.services.media_processing import (
    process_media_asset,
)
from app.services.ownership import (
    get_owned_crop_cycle,
    get_owned_field,
)
from app.storage import get_storage
from app.storage.layout import (
    media_manifest_key,
    media_original_key,
)
from app.storage.manifests import (
    write_media_manifests,
)


router = APIRouter(
    tags=["media"],
)


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
                status.HTTP_422_UNPROCESSABLE_ENTITY
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
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            ),
            detail=(
                f"{media_type.capitalize()} is too large. "
                f"Maximum size is {maximum_mb:.0f} MB."
            ),
        )


def _get_owned_media(
    *,
    media_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
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
    db: DBSession,
    media: MediaAsset,
) -> None:
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


@router.post(
    "/fields/{field_id}/media/uploads",
    response_model=MediaUploadTarget,
    status_code=(
        status.HTTP_201_CREATED
    ),
)
def create_media_upload(
    field_id: UUID,
    data: MediaUploadCreate,
    db: DBSession,
    current_user: CurrentUser,
) -> MediaUploadTarget:
    field = get_owned_field(
        db=db,
        user_id=current_user.id,
        field_id=field_id,
    )

    farm = db.scalar(
        select(Farm).where(
            Farm.id
            == field.farm_id
        )
    )

    if farm is None:
        raise HTTPException(
            status_code=500,
            detail=(
                "Farm hierarchy is missing."
            ),
        )

    normalized_content_type = (
        _normalized_content_type(
            data.content_type
        )
    )

    (
        media_type,
        extension,
    ) = _media_type_info(
        normalized_content_type
    )

    _validate_size(
        media_type=media_type,
        size_bytes=data.size_bytes,
    )

    activity: Activity | None = None

    if data.activity_id is not None:
        activity = db.scalar(
            select(Activity).where(
                Activity.id
                == data.activity_id
            )
        )

        if (
            activity is None
            or activity.field_id
            != field.id
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
                detail=(
                    "The selected activity does not "
                    "belong to this field."
                ),
            )

    crop_cycle_id = (
        data.crop_cycle_id
    )

    if (
        crop_cycle_id is None
        and activity is not None
    ):
        crop_cycle_id = (
            activity.crop_cycle_id
        )

    if crop_cycle_id is not None:
        crop_cycle = get_owned_crop_cycle(
            db=db,
            user_id=current_user.id,
            crop_cycle_id=(
                crop_cycle_id
            ),
        )

        if (
            crop_cycle.field_id
            != field.id
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
                detail=(
                    "The selected crop cycle "
                    "does not belong to this field."
                ),
            )

        if (
            activity is not None
            and activity.crop_cycle_id
            is not None
            and crop_cycle.id
            != activity.crop_cycle_id
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
                detail=(
                    "Activity and crop cycle "
                    "do not match."
                ),
            )

    media_id = uuid4()

    storage_date = (
        data.captured_at.date()
        if data.captured_at
        is not None
        else datetime.now(
            timezone.utc
        ).date()
    )

    object_key = media_original_key(
        user_id=current_user.id,
        farm_slug=farm.storage_slug,
        farm_id=farm.id,
        field_slug=field.storage_slug,
        field_id=field.id,
        storage_date=storage_date,
        media_id=media_id,
        extension=extension,
    )

    media = MediaAsset(
        id=media_id,
        uploaded_by_user_id=(
            current_user.id
        ),
        field_id=field.id,
        activity_id=(
            activity.id
            if activity is not None
            else None
        ),
        crop_cycle_id=(
            crop_cycle_id
        ),
        media_type=media_type,
        status="pending",
        object_key=object_key,
        preview_object_key=None,
        original_filename=(
            Path(
                data.original_filename
            ).name
        ),
        content_type=(
            normalized_content_type
        ),
        size_bytes=(
            data.size_bytes
        ),
        captured_at=(
            data.captured_at
        ),
        width=None,
        height=None,
        duration_seconds=None,
        caption=data.caption,
        metadata_json={
            "storage_date":
                storage_date.isoformat(),
        },
    )

    db.add(media)
    db.commit()
    db.refresh(media)

    upload_url = (
        get_storage()
        .create_signed_upload_url(
            object_key=object_key,
            content_type=(
                normalized_content_type
            ),
            expires_minutes=(
                settings
                .media_upload_url_expiry_minutes
            ),
        )
    )

    return MediaUploadTarget(
        media=_to_response(
            media
        ),
        upload_url=upload_url,
        upload_headers={
            "Content-Type":
                normalized_content_type,
        },
    )


@router.post(
    "/media/{media_id}/complete",
    response_model=(
        MediaAssetResponse
    ),
)
def complete_media_upload(
    media_id: UUID,
    background_tasks: BackgroundTasks,
    db: DBSession,
    current_user: CurrentUser,
) -> MediaAssetResponse:
    media = _get_owned_media(
        media_id=media_id,
        db=db,
        current_user=current_user,
    )

    if media.status == "ready":
        _queue_derivative_processing(
            media=media,
            background_tasks=(
                background_tasks
            ),
        )

        db.commit()
        db.refresh(media)

        _write_manifests_best_effort(
            db=db,
            media=media,
        )

        return _to_response(
            media
        )

    if media.status != "pending":
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "Media upload cannot "
                "be completed."
            ),
        )

    storage = get_storage()

    info = storage.stat(
        media.object_key
    )

    if info is None:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "Uploaded object was "
                "not found."
            ),
        )

    if (
        info.size_bytes
        != media.size_bytes
    ):
        storage.delete(
            media.object_key
        )

        media.status = "failed"

        db.commit()

        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Uploaded file size "
                "did not match the "
                "declared size."
            ),
        )

    media.status = "ready"

    media.metadata_json = {
        **(
            media.metadata_json
            or {}
        ),
    }

    _queue_derivative_processing(
        media=media,
        background_tasks=(
            background_tasks
        ),
    )

    db.commit()
    db.refresh(media)

    _write_manifests_best_effort(
        db=db,
        media=media,
    )

    return _to_response(
        media
    )


@router.post(
    "/media/{media_id}/process",
    response_model=(
        MediaAssetResponse
    ),
)
def retry_media_processing(
    media_id: UUID,
    background_tasks: BackgroundTasks,
    db: DBSession,
    current_user: CurrentUser,
) -> MediaAssetResponse:
    media = _get_owned_media(
        media_id=media_id,
        db=db,
        current_user=current_user,
    )

    if media.status != "ready":
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "Only ready media can "
                "be processed."
            ),
        )

    media.metadata_json = {
        **(
            media.metadata_json
            or {}
        ),
        "derivative_status":
            "queued",
        "derivative_error":
            None,
    }

    db.commit()
    db.refresh(media)

    background_tasks.add_task(
        process_media_asset,
        media.id,
        force=True,
    )

    return _to_response(
        media
    )


@router.get(
    "/fields/{field_id}/media",
    response_model=(
        list[MediaAssetResponse]
    ),
)
def list_field_media(
    field_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    activity_id: UUID | None = Query(
        default=None,
    ),
    unlinked_only: bool = Query(
        default=False,
    ),
) -> list[MediaAssetResponse]:
    get_owned_field(
        db=db,
        user_id=current_user.id,
        field_id=field_id,
    )

    statement = (
        select(MediaAsset)
        .where(
            MediaAsset.field_id
            == field_id,
            MediaAsset.status
            == "ready",
        )
        .order_by(
            MediaAsset.captured_at
            .desc()
            .nullslast(),
            MediaAsset.created_at
            .desc(),
        )
    )

    if activity_id is not None:
        statement = statement.where(
            MediaAsset.activity_id
            == activity_id
        )

    elif unlinked_only:
        statement = statement.where(
            MediaAsset.activity_id
            .is_(None)
        )

    return [
        _to_response(
            media
        )
        for media
        in db.scalars(
            statement
        ).all()
    ]


@router.get(
    "/media/{media_id}",
    response_model=(
        MediaAssetResponse
    ),
)
def get_media(
    media_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> MediaAssetResponse:
    return _to_response(
        _get_owned_media(
            media_id=media_id,
            db=db,
            current_user=current_user,
        )
    )


@router.get(
    "/media/{media_id}/content",
)
def get_media_content(
    media_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    media = _get_owned_media(
        media_id=media_id,
        db=db,
        current_user=current_user,
    )

    if media.status != "ready":
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail="Media is not ready.",
        )

    return RedirectResponse(
        url=(
            get_storage()
            .create_signed_download_url(
                object_key=(
                    media.object_key
                ),
                expires_minutes=(
                    settings
                    .media_download_url_expiry_minutes
                ),
            )
        ),
        status_code=(
            status.HTTP_307_TEMPORARY_REDIRECT
        ),
    )


@router.get(
    "/media/{media_id}/preview",
)
def get_media_preview(
    media_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    media = _get_owned_media(
        media_id=media_id,
        db=db,
        current_user=current_user,
    )

    if not media.preview_object_key:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Media preview is "
                "not available yet."
            ),
        )

    return RedirectResponse(
        url=(
            get_storage()
            .create_signed_download_url(
                object_key=(
                    media.preview_object_key
                ),
                expires_minutes=(
                    settings
                    .media_download_url_expiry_minutes
                ),
            )
        ),
        status_code=(
            status.HTTP_307_TEMPORARY_REDIRECT
        ),
    )


@router.delete(
    "/media/{media_id}",
    status_code=(
        status.HTTP_204_NO_CONTENT
    ),
)
def delete_media(
    media_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> Response:
    media = _get_owned_media(
        media_id=media_id,
        db=db,
        current_user=current_user,
    )

    storage = get_storage()

    storage.delete(
        media.object_key
    )

    if media.preview_object_key:
        storage.delete(
            media.preview_object_key
        )

    storage.delete(
        media_manifest_key(
            media.object_key
        )
    )

    db.delete(media)
    db.commit()

    return Response(
        status_code=(
            status.HTTP_204_NO_CONTENT
        )
    )
