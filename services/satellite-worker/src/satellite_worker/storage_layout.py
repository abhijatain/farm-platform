
from __future__ import annotations

from datetime import date
from uuid import UUID


STORAGE_LAYOUT_VERSION = 2


def user_root(
    context: dict,
) -> str:
    return (
        f"users/{context['user_id']}"
    )


def farm_root(
    context: dict,
) -> str:
    return (
        f"{user_root(context)}/farms/"
        f"{context['farm_storage_slug']}__{context['farm_id']}"
    )


def field_root(
    context: dict,
) -> str:
    return (
        f"{farm_root(context)}/fields/"
        f"{context['field_storage_slug']}__{context['field_id']}"
    )


def dated_field_root(
    context: dict,
    storage_date: date,
) -> str:
    return (
        f"{field_root(context)}/dates/"
        f"{storage_date.year:04d}/"
        f"{storage_date.month:02d}/"
        f"{storage_date.day:02d}"
    )


def satellite_prefix(
    *,
    context: dict,
    observed_on: date,
    observation_id: UUID,
) -> str:
    return (
        f"{dated_field_root(context, observed_on)}"
        f"/satellite/{observation_id}"
    )


def satellite_metric_key(
    *,
    context: dict,
    observed_on: date,
    observation_id: UUID,
    metric_type: str,
) -> str:
    return (
        f"{satellite_prefix(context=context, observed_on=observed_on, observation_id=observation_id)}"
        f"/{metric_type.strip().lower()}.tif"
    )


def media_prefix(
    *,
    context: dict,
    storage_date: date,
    media_id: UUID,
) -> str:
    return (
        f"{dated_field_root(context, storage_date)}"
        f"/media/{media_id}"
    )


def user_manifest_key(
    context: dict,
) -> str:
    return (
        f"{user_root(context)}/user.json"
    )


def farm_manifest_key(
    context: dict,
) -> str:
    return (
        f"{farm_root(context)}/farm.json"
    )


def field_manifest_key(
    context: dict,
) -> str:
    return (
        f"{field_root(context)}/field.json"
    )
