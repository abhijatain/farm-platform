
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import UUID

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.media_asset import MediaAsset
from app.storage import get_storage
from app.storage.manifests import write_media_manifests


register_heif_opener()


EXIF_DATETIME_ORIGINAL = 36867
EXIF_DATETIME = 306
EXIF_OFFSET_TIME = 36880
EXIF_OFFSET_TIME_ORIGINAL = 36881


def _processing_metadata(
    current: dict | None,
    **updates,
) -> dict:
    return {
        **(current or {}),
        **updates,
    }


def _parse_exif_capture_time(
    image: Image.Image,
) -> tuple[
    datetime | None,
    dict,
]:
    exif = image.getexif()

    if not exif:
        return None, {}

    raw_datetime = (
        exif.get(
            EXIF_DATETIME_ORIGINAL
        )
        or exif.get(
            EXIF_DATETIME
        )
    )

    raw_offset = (
        exif.get(
            EXIF_OFFSET_TIME_ORIGINAL
        )
        or exif.get(
            EXIF_OFFSET_TIME
        )
    )

    metadata: dict = {}

    if raw_datetime:
        metadata[
            "exif_datetime_original"
        ] = str(
            raw_datetime
        )

    if raw_offset:
        metadata[
            "exif_offset_time"
        ] = str(
            raw_offset
        )

    if not raw_datetime:
        return None, metadata

    try:
        parsed = datetime.strptime(
            str(raw_datetime),
            "%Y:%m:%d %H:%M:%S",
        )
    except ValueError:
        return None, metadata

    if not raw_offset:
        # EXIF often has no timezone.
        # Keep the raw value as metadata rather than
        # pretending we know the timezone.
        return None, metadata

    try:
        offset_tz = datetime.strptime(
            str(raw_offset),
            "%z",
        ).tzinfo

        parsed = parsed.replace(
            tzinfo=offset_tz
        )

        return parsed, metadata

    except ValueError:
        return None, metadata


def _thumbnail_key(
    media: MediaAsset,
) -> str:
    base = media.object_key.rsplit(
        "/",
        maxsplit=1,
    )[0]

    return (
        f"{base}/thumbnail.webp"
    )


def _video_poster_key(
    media: MediaAsset,
) -> str:
    base = media.object_key.rsplit(
        "/",
        maxsplit=1,
    )[0]

    return (
        f"{base}/poster.jpg"
    )


def _materialize_original(
    *,
    media: MediaAsset,
    temporary_dir: Path,
) -> Path:
    storage = get_storage()

    extension = (
        Path(
            media.original_filename
        ).suffix
        or Path(
            media.object_key
        ).suffix
        or ".bin"
    )

    destination = (
        temporary_dir
        / f"original{extension}"
    )

    return storage.download_file(
        object_key=media.object_key,
        destination_path=destination,
    )


def _process_image(
    *,
    media: MediaAsset,
    source_path: Path,
    temporary_dir: Path,
) -> dict:
    storage = get_storage()

    output_path = (
        temporary_dir
        / "thumbnail.webp"
    )

    with Image.open(
        source_path
    ) as source_image:
        (
            captured_at,
            exif_metadata,
        ) = _parse_exif_capture_time(
            source_image
        )

        oriented = (
            ImageOps.exif_transpose(
                source_image
            )
        )

        width, height = (
            oriented.size
        )

        thumbnail = oriented.copy()

        thumbnail.thumbnail(
            (
                settings
                .media_thumbnail_max_pixels,
                settings
                .media_thumbnail_max_pixels,
            ),
            Image.Resampling.LANCZOS,
        )

        if thumbnail.mode not in (
            "RGB",
            "RGBA",
        ):
            thumbnail = (
                thumbnail.convert(
                    "RGB"
                )
            )

        thumbnail.save(
            output_path,
            format="WEBP",
            quality=(
                settings
                .media_thumbnail_webp_quality
            ),
            method=6,
        )

    thumbnail_key = (
        _thumbnail_key(
            media
        )
    )

    storage.upload_file(
        source_path=output_path,
        object_key=thumbnail_key,
        content_type="image/webp",
    )

    return {
        "width": width,
        "height": height,
        "duration_seconds": None,
        "captured_at": captured_at,
        "preview_object_key": (
            thumbnail_key
        ),
        "metadata": {
            **exif_metadata,
            "derivative_kind": (
                "image_thumbnail"
            ),
            "thumbnail_format": (
                "webp"
            ),
        },
    }


def _run_ffprobe(
    source_path: Path,
) -> dict:
    executable = shutil.which(
        settings.ffprobe_binary
    )

    if executable is None:
        raise RuntimeError(
            "ffprobe was not found. "
            "Install FFmpeg or set FFPROBE_BINARY."
        )

    completed = subprocess.run(
        [
            executable,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(source_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    return json.loads(
        completed.stdout
    )


def _video_creation_time(
    probe: dict,
) -> datetime | None:
    candidates: list[str] = []

    for stream in (
        probe.get(
            "streams",
            []
        )
        or []
    ):
        tags = (
            stream.get(
                "tags",
                {}
            )
            or {}
        )

        value = tags.get(
            "creation_time"
        )

        if value:
            candidates.append(
                str(value)
            )

    format_tags = (
        (
            probe.get(
                "format",
                {}
            )
            or {}
        ).get(
            "tags",
            {}
        )
        or {}
    )

    value = format_tags.get(
        "creation_time"
    )

    if value:
        candidates.append(
            str(value)
        )

    for candidate in candidates:
        try:
            parsed = (
                datetime.fromisoformat(
                    candidate.replace(
                        "Z",
                        "+00:00",
                    )
                )
            )

            if (
                parsed.tzinfo
                is not None
            ):
                return parsed

        except ValueError:
            continue

    return None


def _video_properties(
    probe: dict,
) -> tuple[
    int | None,
    int | None,
    float | None,
]:
    streams = (
        probe.get(
            "streams",
            []
        )
        or []
    )

    video_stream = next(
        (
            stream
            for stream in streams
            if stream.get(
                "codec_type"
            )
            == "video"
        ),
        None,
    )

    if video_stream is None:
        return (
            None,
            None,
            None,
        )

    width = video_stream.get(
        "width"
    )

    height = video_stream.get(
        "height"
    )

    rotation = None

    tags = (
        video_stream.get(
            "tags",
            {}
        )
        or {}
    )

    if tags.get("rotate"):
        try:
            rotation = int(
                tags["rotate"]
            )
        except (
            TypeError,
            ValueError,
        ):
            rotation = None

    if (
        rotation is not None
        and abs(rotation) % 180
        == 90
    ):
        width, height = (
            height,
            width,
        )

    duration_raw = (
        video_stream.get(
            "duration"
        )
        or (
            probe.get(
                "format",
                {}
            )
            or {}
        ).get(
            "duration"
        )
    )

    duration = None

    if duration_raw is not None:
        try:
            duration = float(
                duration_raw
            )
        except (
            TypeError,
            ValueError,
        ):
            duration = None

    return (
        int(width)
        if width is not None
        else None,
        int(height)
        if height is not None
        else None,
        duration,
    )


def _create_video_poster(
    *,
    source_path: Path,
    output_path: Path,
    duration_seconds: float | None,
) -> None:
    executable = shutil.which(
        settings.ffmpeg_binary
    )

    if executable is None:
        raise RuntimeError(
            "ffmpeg was not found. "
            "Install FFmpeg or set FFMPEG_BINARY."
        )

    seek_seconds = 0.0

    if (
        duration_seconds is not None
        and duration_seconds > 1.0
    ):
        seek_seconds = min(
            1.0,
            duration_seconds * 0.1,
        )

    subprocess.run(
        [
            executable,
            "-y",
            "-ss",
            f"{seek_seconds:.3f}",
            "-i",
            str(source_path),
            "-frames:v",
            "1",
            "-vf",
            (
                "scale="
                f"{settings.media_video_poster_max_pixels}:"
                f"{settings.media_video_poster_max_pixels}:"
                "force_original_aspect_ratio=decrease"
            ),
            "-q:v",
            "3",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )


def _process_video(
    *,
    media: MediaAsset,
    source_path: Path,
    temporary_dir: Path,
) -> dict:
    storage = get_storage()

    probe = _run_ffprobe(
        source_path
    )

    (
        width,
        height,
        duration_seconds,
    ) = _video_properties(
        probe
    )

    captured_at = (
        _video_creation_time(
            probe
        )
    )

    poster_path = (
        temporary_dir
        / "poster.jpg"
    )

    _create_video_poster(
        source_path=source_path,
        output_path=poster_path,
        duration_seconds=(
            duration_seconds
        ),
    )

    poster_key = (
        _video_poster_key(
            media
        )
    )

    storage.upload_file(
        source_path=poster_path,
        object_key=poster_key,
        content_type="image/jpeg",
    )

    return {
        "width": width,
        "height": height,
        "duration_seconds": (
            duration_seconds
        ),
        "captured_at": captured_at,
        "preview_object_key": (
            poster_key
        ),
        "metadata": {
            "derivative_kind": (
                "video_poster"
            ),
            "poster_format": (
                "jpeg"
            ),
        },
    }


def process_media_asset(
    media_id: UUID,
    *,
    force: bool = False,
) -> None:
    db = SessionLocal()

    try:
        media = db.scalar(
            select(
                MediaAsset
            ).where(
                MediaAsset.id
                == media_id
            )
        )

        if media is None:
            return

        if media.status != "ready":
            return

        current_metadata = (
            media.metadata_json
            or {}
        )

        if (
            not force
            and current_metadata.get(
                "derivative_status"
            )
            == "complete"
            and media.preview_object_key
        ):
            return

        media.metadata_json = (
            _processing_metadata(
                current_metadata,
                derivative_status=(
                    "processing"
                ),
                derivative_error=None,
            )
        )

        db.commit()

        with tempfile.TemporaryDirectory(
            prefix="farm-media-"
        ) as temporary:
            temporary_dir = Path(
                temporary
            )

            source_path = (
                _materialize_original(
                    media=media,
                    temporary_dir=(
                        temporary_dir
                    ),
                )
            )

            if media.media_type == "image":
                result = _process_image(
                    media=media,
                    source_path=source_path,
                    temporary_dir=(
                        temporary_dir
                    ),
                )

            elif media.media_type == "video":
                result = _process_video(
                    media=media,
                    source_path=source_path,
                    temporary_dir=(
                        temporary_dir
                    ),
                )

            else:
                raise RuntimeError(
                    "Unsupported media type: "
                    f"{media.media_type}"
                )

        media.width = result[
            "width"
        ]

        media.height = result[
            "height"
        ]

        media.duration_seconds = (
            result[
                "duration_seconds"
            ]
        )

        if (
            media.captured_at is None
            and result[
                "captured_at"
            ]
            is not None
        ):
            media.captured_at = (
                result[
                    "captured_at"
                ]
            )

        media.preview_object_key = (
            result[
                "preview_object_key"
            ]
        )

        media.metadata_json = (
            _processing_metadata(
                media.metadata_json,
                **result[
                    "metadata"
                ],
                derivative_status=(
                    "complete"
                ),
                derivative_error=None,
            )
        )

        db.commit()
        db.refresh(media)

        try:
            write_media_manifests(
                db=db,
                media=media,
            )
        except Exception as manifest_error:
            print(
                "Media manifest write failed after processing: "
                f"{type(manifest_error).__name__}: "
                f"{manifest_error}"
            )

    except Exception as error:
        db.rollback()

        media = db.scalar(
            select(
                MediaAsset
            ).where(
                MediaAsset.id
                == media_id
            )
        )

        if media is not None:
            media.metadata_json = (
                _processing_metadata(
                    media.metadata_json,
                    derivative_status=(
                        "failed"
                    ),
                    derivative_error=(
                        str(error)[:1000]
                    ),
                )
            )

            db.commit()
            db.refresh(media)

            try:
                write_media_manifests(
                    db=db,
                    media=media,
                )
            except Exception as manifest_error:
                print(
                    "Media manifest write failed after processing error: "
                    f"{type(manifest_error).__name__}: "
                    f"{manifest_error}"
                )

    finally:
        db.close()
