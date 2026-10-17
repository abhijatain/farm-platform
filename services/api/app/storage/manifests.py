"""Maintain object recovery manifests independent of operational database availability."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from uuid import UUID

from geoalchemy2.shape import to_shape
from shapely.geometry import mapping
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.models.crop_cycle import CropCycle
from app.models.farm import Farm
from app.models.field import Field
from app.models.media_asset import MediaAsset
from app.models.user import User
from app.storage import GCSStorage, get_storage
from app.storage.layout import (
    STORAGE_LAYOUT_VERSION,
    farm_manifest_key,
    field_manifest_key,
    media_manifest_key,
    user_manifest_key,
)


def _json_default(
    value,
):
    if isinstance(
        value,
        (
            datetime,
            date,
        ),
    ):
        return value.isoformat()

    if isinstance(
        value,
        UUID,
    ):
        return str(value)

    raise TypeError(
        f"Unsupported JSON value: {type(value).__name__}"
    )


def _write_json(
    *,
    storage: GCSStorage,
    object_key: str,
    payload: dict,
) -> None:
    raw = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        default=_json_default,
    ).encode("utf-8")

    storage.upload_bytes(
        data=raw,
        object_key=object_key,
        content_type="application/json",
    )


def _storage_date(
    media: MediaAsset,
) -> date:
    metadata = (
        media.metadata_json
        or {}
    )

    raw = metadata.get(
        "storage_date"
    )

    if isinstance(
        raw,
        str,
    ):
        try:
            return date.fromisoformat(
                raw
            )
        except ValueError:
            pass

    if media.captured_at is not None:
        return media.captured_at.date()

    return media.created_at.date()


def _hierarchy(
    db: Session,
    media: MediaAsset,
) -> tuple[
    User,
    Farm,
    Field,
]:
    user = db.scalar(
        select(User).where(
            User.id
            == media.uploaded_by_user_id
        )
    )

    field = db.scalar(
        select(Field).where(
            Field.id
            == media.field_id
        )
    )

    if (
        user is None
        or field is None
    ):
        raise RuntimeError(
            "Media hierarchy could not be resolved."
        )

    farm = db.scalar(
        select(Farm).where(
            Farm.id
            == field.farm_id
        )
    )

    if farm is None:
        raise RuntimeError(
            "Media farm could not be resolved."
        )

    return (
        user,
        farm,
        field,
    )


def write_media_manifests(
    *,
    db: Session,
    media: MediaAsset,
) -> None:
    (
        user,
        farm,
        field,
    ) = _hierarchy(
        db,
        media,
    )

    storage = get_storage()

    now = datetime.now(
        timezone.utc
    ).isoformat()

    _write_json(
        storage=storage,
        object_key="storage-layout.json",
        payload={
            "schema": "farm-platform-object-storage",
            "storage_layout_version": STORAGE_LAYOUT_VERSION,
            "root_prefix": "users/",
            "generated_at": now,
            "note": (
                "PostgreSQL is the operational database. "
                "These manifests make object data portable and recoverable."
            ),
        },
    )

    _write_json(
        storage=storage,
        object_key=user_manifest_key(
            user.id
        ),
        payload={
            "manifest_type": "user",
            "storage_layout_version": STORAGE_LAYOUT_VERSION,
            "user_id": str(user.id),
            # Identity/phone remain only in Firebase and PostgreSQL.
            "preferred_language": user.preferred_language,
            "updated_at": now,
        },
    )

    _write_json(
        storage=storage,
        object_key=farm_manifest_key(
            user_id=user.id,
            farm_slug=farm.storage_slug,
            farm_id=farm.id,
        ),
        payload={
            "manifest_type": "farm",
            "storage_layout_version": STORAGE_LAYOUT_VERSION,
            "user_id": str(user.id),
            "farm_id": str(farm.id),
            "name": farm.name,
            "storage_slug": farm.storage_slug,
            "location_name": farm.location_name,
            "created_at": farm.created_at,
            "updated_at": farm.updated_at,
        },
    )

    boundary = mapping(
        to_shape(
            field.boundary
        )
    )

    _write_json(
        storage=storage,
        object_key=field_manifest_key(
            user_id=user.id,
            farm_slug=farm.storage_slug,
            farm_id=farm.id,
            field_slug=field.storage_slug,
            field_id=field.id,
        ),
        payload={
            "manifest_type": "field",
            "storage_layout_version": STORAGE_LAYOUT_VERSION,
            "user_id": str(user.id),
            "farm_id": str(farm.id),
            "field_id": str(field.id),
            "name": field.name,
            "storage_slug": field.storage_slug,
            "boundary": boundary,
            "created_at": field.created_at,
            "updated_at": field.updated_at,
        },
    )

    activity = None

    if media.activity_id is not None:
        activity = db.scalar(
            select(Activity).where(
                Activity.id
                == media.activity_id
            )
        )

    crop_cycle = None

    if media.crop_cycle_id is not None:
        crop_cycle = db.scalar(
            select(CropCycle).where(
                CropCycle.id
                == media.crop_cycle_id
            )
        )

    files: dict = {
        "original": {
            "object_key": media.object_key,
            "uri": storage.object_uri(
                media.object_key
            ),
            "content_type": media.content_type,
            "size_bytes": media.size_bytes,
        }
    }

    if media.preview_object_key:
        files["preview"] = {
            "object_key": media.preview_object_key,
            "uri": storage.object_uri(
                media.preview_object_key
            ),
        }

    activity_snapshot = None

    if activity is not None:
        activity_snapshot = {
            "activity_id": str(activity.id),
            "activity_type": activity.activity_type,
            "occurred_at": activity.occurred_at,
            "notes": activity.notes,
            "details": activity.details,
        }

    crop_cycle_snapshot = None

    if crop_cycle is not None:
        crop_cycle_snapshot = {
            "crop_cycle_id": str(
                crop_cycle.id
            ),
            "season_id": str(
                crop_cycle.season_id
            ),
            "crop_name": crop_cycle.crop_name,
            "variety": crop_cycle.variety,
            "status": crop_cycle.status,
            "started_on": crop_cycle.started_on,
            "planted_on": crop_cycle.planted_on,
            "expected_harvest_on": crop_cycle.expected_harvest_on,
            "harvested_on": crop_cycle.harvested_on,
            "yield_kg": crop_cycle.yield_kg,
            "harvested_area_acres": crop_cycle.harvested_area_acres,
            "moisture_percent": crop_cycle.moisture_percent,
            "quality_grade": crop_cycle.quality_grade,
            "selling_price_per_kg": crop_cycle.selling_price_per_kg,
            "harvest_notes": crop_cycle.harvest_notes,
        }

    _write_json(
        storage=storage,
        object_key=media_manifest_key(
            media.object_key
        ),
        payload={
            "manifest_type": "media_asset",
            "storage_layout_version": STORAGE_LAYOUT_VERSION,
            "media_id": str(media.id),
            "user_id": str(user.id),
            "farm_id": str(farm.id),
            "field_id": str(field.id),
            "activity_id": (
                str(media.activity_id)
                if media.activity_id
                else None
            ),
            "crop_cycle_id": (
                str(media.crop_cycle_id)
                if media.crop_cycle_id
                else None
            ),
            "storage_date": _storage_date(
                media
            ),
            "media_type": media.media_type,
            "status": media.status,
            "original_filename": media.original_filename,
            "content_type": media.content_type,
            "size_bytes": media.size_bytes,
            "captured_at": media.captured_at,
            "width": media.width,
            "height": media.height,
            "duration_seconds": media.duration_seconds,
            "caption": media.caption,
            "activity": activity_snapshot,
            "crop_cycle": crop_cycle_snapshot,
            "files": files,
            "metadata": media.metadata_json,
            "created_at": media.created_at,
            "updated_at": media.updated_at,
            "manifest_generated_at": now,
        },
    )
