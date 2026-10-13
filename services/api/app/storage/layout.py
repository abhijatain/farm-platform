
from __future__ import annotations

from datetime import date
from uuid import UUID


STORAGE_LAYOUT_VERSION = 2


def user_root(
    user_id: UUID,
) -> str:
    return f"users/{user_id}"


def farm_root(
    *,
    user_id: UUID,
    farm_slug: str,
    farm_id: UUID,
) -> str:
    return (
        f"{user_root(user_id)}/farms/"
        f"{farm_slug}__{farm_id}"
    )


def field_root(
    *,
    user_id: UUID,
    farm_slug: str,
    farm_id: UUID,
    field_slug: str,
    field_id: UUID,
) -> str:
    return (
        f"{farm_root(user_id=user_id, farm_slug=farm_slug, farm_id=farm_id)}"
        f"/fields/{field_slug}__{field_id}"
    )


def dated_field_root(
    *,
    user_id: UUID,
    farm_slug: str,
    farm_id: UUID,
    field_slug: str,
    field_id: UUID,
    storage_date: date,
) -> str:
    return (
        f"{field_root(user_id=user_id, farm_slug=farm_slug, farm_id=farm_id, field_slug=field_slug, field_id=field_id)}"
        f"/dates/{storage_date.year:04d}/{storage_date.month:02d}/{storage_date.day:02d}"
    )


def media_prefix(
    *,
    user_id: UUID,
    farm_slug: str,
    farm_id: UUID,
    field_slug: str,
    field_id: UUID,
    storage_date: date,
    media_id: UUID,
) -> str:
    return (
        f"{dated_field_root(user_id=user_id, farm_slug=farm_slug, farm_id=farm_id, field_slug=field_slug, field_id=field_id, storage_date=storage_date)}"
        f"/media/{media_id}"
    )


def media_original_key(
    *,
    user_id: UUID,
    farm_slug: str,
    farm_id: UUID,
    field_slug: str,
    field_id: UUID,
    storage_date: date,
    media_id: UUID,
    extension: str,
) -> str:
    ext = (
        extension
        if extension.startswith(".")
        else f".{extension}"
    )

    return (
        f"{media_prefix(user_id=user_id, farm_slug=farm_slug, farm_id=farm_id, field_slug=field_slug, field_id=field_id, storage_date=storage_date, media_id=media_id)}"
        f"/original{ext.lower()}"
    )


def media_manifest_key(
    object_key: str,
) -> str:
    return (
        f"{object_key.rsplit('/', 1)[0]}"
        "/manifest.json"
    )


def user_manifest_key(
    user_id: UUID,
) -> str:
    return (
        f"{user_root(user_id)}/user.json"
    )


def farm_manifest_key(
    *,
    user_id: UUID,
    farm_slug: str,
    farm_id: UUID,
) -> str:
    return (
        f"{farm_root(user_id=user_id, farm_slug=farm_slug, farm_id=farm_id)}"
        "/farm.json"
    )


def field_manifest_key(
    *,
    user_id: UUID,
    farm_slug: str,
    farm_id: UUID,
    field_slug: str,
    field_id: UUID,
) -> str:
    return (
        f"{field_root(user_id=user_id, farm_slug=farm_slug, farm_id=farm_id, field_slug=field_slug, field_id=field_id)}"
        "/field.json"
    )
