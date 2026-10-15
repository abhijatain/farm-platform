"""Apply reusable ownership checks before reading or writing farm records."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.crop_cycle import CropCycle
from app.models.farm import Farm
from app.models.field import Field
from app.models.season import Season


def get_owned_farm(
    db: Session,
    user_id: UUID,
    farm_id: UUID,
) -> Farm:
    farm = db.scalar(
        select(Farm).where(
            Farm.id == farm_id,
            Farm.owner_user_id == user_id,
        )
    )

    if farm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farm not found.",
        )

    return farm


def get_owned_field(
    db: Session,
    user_id: UUID,
    field_id: UUID,
) -> Field:
    field = db.scalar(
        select(Field)
        .join(
            Farm,
            Farm.id == Field.farm_id,
        )
        .where(
            Field.id == field_id,
            Farm.owner_user_id == user_id,
        )
    )

    if field is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Field not found.",
        )

    return field


def get_owned_season(
    db: Session,
    user_id: UUID,
    season_id: UUID,
) -> Season:
    season = db.scalar(
        select(Season)
        .join(
            Farm,
            Farm.id == Season.farm_id,
        )
        .where(
            Season.id == season_id,
            Farm.owner_user_id == user_id,
        )
    )

    if season is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Season not found.",
        )

    return season


def get_owned_crop_cycle(
    db: Session,
    user_id: UUID,
    crop_cycle_id: UUID,
) -> CropCycle:
    crop_cycle = db.scalar(
        select(CropCycle)
        .join(
            Season,
            Season.id == CropCycle.season_id,
        )
        .join(
            Field,
            Field.id == CropCycle.field_id,
        )
        .join(
            Farm,
            Farm.id == Season.farm_id,
        )
        .where(
            CropCycle.id == crop_cycle_id,
            Farm.owner_user_id == user_id,
            Field.farm_id == Farm.id,
        )
    )

    if crop_cycle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Crop cycle not found.",
        )

    return crop_cycle
