
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
    Request,
    Response,
    status,
)
from fastapi.responses import (
    FileResponse,
    RedirectResponse,
)
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
from app.storage import (
    StorageBackend,
    get_storage,
    get_storage_for_location,
)
from app.storage.layout import (
    STORAGE_LAYOUT_VERSION,
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


def _storage_for_media(
    media: MediaAsset,
) -> StorageBackend:
    return get_storage_for_location(
        storage_backend=(
            media.storage_backend
        ),
        bucket_name=(
            media.bucket_name
        ),
    )


def _signed_download_url(
    media: MediaAsset,
    object_key: str | None,
) -> str | None:
    if not object_key:
        return None

    storage = _storage_for_media(
        media
    )

    return (
        storage
        .create_signed_download_url(
            object_key=object_key,
            expires_minutes=(
                settings
                .media_download_url_expiry_minutes
            ),
        )
    )


def _thumbnail_content_type(
    object_key: str,
) -> str:
    suffix = (
        Path(object_key)
        .suffix
        .lower()
    )

    if suffix == ".webp":
        return "image/webp"

    if suffix in (
        ".jpg",
        ".jpeg",
    ):
        return "image/jpeg"

    if suffix == ".png":
        return "image/png"

    return "application/octet-stream"


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
        storage_backend=(
            media.storage_backend
        ),
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
                media,
                media.object_key,
            )
            if media.status == "ready"
            else None
        ),
        thumbnail_available=(
            media.thumbnail_object_key
            is not None
        ),
        thumbnail_url=(
            _signed_download_url(
                media,
                media.thumbnail_object_key,
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
        and media.thumbnail_object_key
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

    storage = get_storage()

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
        storage_backend=(
            storage.backend_name
        ),
        bucket_name=(
            storage.bucket_name
        ),
        object_key=object_key,
        thumbnail_object_key=None,
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
            "storage_layout_version":
                STORAGE_LAYOUT_VERSION,
            "storage_date":
                storage_date.isoformat(),
        },
    )

    db.add(media)
    db.commit()
    db.refresh(media)

    if (
        storage.backend_name
        == "gcs"
    ):
        signed_url = (
            storage
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

        if signed_url is None:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Unable to create "
                    "GCS upload URL."
                ),
            )

        upload_method = (
            "gcs_signed_put"
        )

        upload_url = signed_url

    else:
        upload_method = "api_put"

        upload_url = (
            f"/media/{media.id}/content"
        )

    return MediaUploadTarget(
        media=_to_response(
            media
        ),
        upload_method=(
            upload_method
        ),
        upload_url=upload_url,
        upload_headers={
            "Content-Type": (
                normalized_content_type
            ),
        },
    )


@router.put(
    "/media/{media_id}/content",
    status_code=(
        status.HTTP_204_NO_CONTENT
    ),
)
async def upload_local_media_content(
    media_id: UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
) -> Response:
    media = _get_owned_media(
        media_id=media_id,
        db=db,
        current_user=current_user,
    )

    if media.status != "pending":
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "Media upload is not pending."
            ),
        )

    storage = _storage_for_media(
        media
    )

    if (
        storage.backend_name
        != "local"
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "Direct API upload is only "
                "available for local storage."
            ),
        )

    request_content_type = (
        _normalized_content_type(
            request.headers.get(
                "content-type",
                "",
            )
        )
    )

    if (
        request_content_type
        and request_content_type
        != media.content_type
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Uploaded Content-Type "
                "does not match the "
                "declared media type."
            ),
        )

    try:
        await storage.put_async_chunks(
            object_key=(
                media.object_key
            ),
            chunks=request.stream(),
            content_type=(
                media.content_type
            ),
            expected_size=(
                media.size_bytes
            ),
            max_size=_maximum_size(
                media.media_type
            ),
        )

    except ValueError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(error),
        )

    return Response(
        status_code=(
            status.HTTP_204_NO_CONTENT
        )
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

    storage = _storage_for_media(
        media
    )

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
        "storage_etag":
            info.etag,
        "storage_layout_version":
            STORAGE_LAYOUT_VERSION,
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

    rows = db.scalars(
        statement
    ).all()

    return [
        _to_response(
            media
        )
        for media in rows
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
    media = _get_owned_media(
        media_id=media_id,
        db=db,
        current_user=current_user,
    )

    return _to_response(
        media
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

    storage = _storage_for_media(
        media
    )

    signed_url = (
        storage
        .create_signed_download_url(
            object_key=(
                media.object_key
            ),
            expires_minutes=(
                settings
                .media_download_url_expiry_minutes
            ),
        )
    )

    if signed_url is not None:
        return RedirectResponse(
            url=signed_url,
            status_code=(
                status.HTTP_307_TEMPORARY_REDIRECT
            ),
        )

    local_path = storage.local_path(
        media.object_key
    )

    if local_path is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Media object not found."
            ),
        )

    return FileResponse(
        path=local_path,
        media_type=(
            media.content_type
        ),
        filename=(
            media.original_filename
        ),
        content_disposition_type="inline",
    )


@router.get(
    "/media/{media_id}/thumbnail",
)
def get_media_thumbnail(
    media_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    media = _get_owned_media(
        media_id=media_id,
        db=db,
        current_user=current_user,
    )

    if not (
        media.thumbnail_object_key
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Media thumbnail is "
                "not available yet."
            ),
        )

    storage = _storage_for_media(
        media
    )

    signed_url = (
        storage
        .create_signed_download_url(
            object_key=(
                media.thumbnail_object_key
            ),
            expires_minutes=(
                settings
                .media_download_url_expiry_minutes
            ),
        )
    )

    if signed_url is not None:
        return RedirectResponse(
            url=signed_url,
            status_code=(
                status.HTTP_307_TEMPORARY_REDIRECT
            ),
        )

    local_path = storage.local_path(
        media.thumbnail_object_key
    )

    if local_path is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Media thumbnail object "
                "was not found."
            ),
        )

    return FileResponse(
        path=local_path,
        media_type=(
            _thumbnail_content_type(
                media.thumbnail_object_key
            )
        ),
        content_disposition_type="inline",
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

    storage = _storage_for_media(
        media
    )

    storage.delete(
        media.object_key
    )

    if (
        media.thumbnail_object_key
    ):
        storage.delete(
            media.thumbnail_object_key
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
