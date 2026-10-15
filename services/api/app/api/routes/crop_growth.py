"""Farmer-confirmed stage transitions with independent provisional context."""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DBSession
from app.models.crop_stage_observation import CropStageObservation
from app.models.field import Field
from app.schemas.crop_growth import (
    CropGrowthResponse,
    StageObservationInput,
    StageObservationResponse,
)
from app.services.crop_growth import make_crop_growth_response
from app.domains.crops.phenology import resolve_profile
from app.services.ownership import get_owned_crop_cycle
from app.services.weather import _today


router = APIRouter(tags=["crop growth"])


def _observations(db: DBSession, crop_cycle_id: UUID) -> list[CropStageObservation]:
    return list(db.scalars(
        select(CropStageObservation)
        .where(CropStageObservation.crop_cycle_id == crop_cycle_id)
        .order_by(CropStageObservation.observed_on.asc())
    ).all())


@router.get(
    "/crop-cycles/{crop_cycle_id}/growth-stages",
    response_model=CropGrowthResponse,
)
def get_growth_stages(
    crop_cycle_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> CropGrowthResponse:
    crop_cycle = get_owned_crop_cycle(
        db=db, user_id=current_user.id, crop_cycle_id=crop_cycle_id,
    )
    point = db.execute(
        select(
            func.ST_Y(func.ST_Centroid(Field.boundary)),
            func.ST_X(func.ST_Centroid(Field.boundary)),
        ).where(Field.id == crop_cycle.field_id)
    ).one()
    return make_crop_growth_response(
        crop_cycle=crop_cycle,
        observations=_observations(db, crop_cycle.id),
        latitude=float(point[0]),
        longitude=float(point[1]),
        today=_today(),
    )


@router.put(
    "/crop-cycles/{crop_cycle_id}/growth-stages",
    response_model=StageObservationResponse,
)
def record_growth_stage(
    crop_cycle_id: UUID,
    data: StageObservationInput,
    db: DBSession,
    current_user: CurrentUser,
) -> CropStageObservation:
    cycle = get_owned_crop_cycle(
        db=db, user_id=current_user.id, crop_cycle_id=crop_cycle_id,
    )
    stages = resolve_profile(cycle.crop_name).stages
    ranking = {stage.code: index for index, stage in enumerate(stages)}
    if data.stage_code not in ranking:
        raise HTTPException(status_code=422, detail="Stage is not valid for this crop profile.")
    earliest = cycle.planted_on or cycle.started_on
    if data.observed_on < earliest:
        raise HTTPException(status_code=422, detail="Stage date cannot precede crop start or planting.")
    if data.observed_on > _today():
        raise HTTPException(status_code=422, detail="Future stages cannot be recorded as observed.")
    if cycle.harvested_on and data.observed_on > cycle.harvested_on:
        raise HTTPException(status_code=422, detail="Observed stage date cannot be after harvest.")

    existing = _observations(db, cycle.id)
    for other in existing:
        if other.stage_code == data.stage_code:
            continue
        if (
            ranking[other.stage_code] < ranking[data.stage_code]
            and other.observed_on > data.observed_on
        ) or (
            ranking[other.stage_code] > ranking[data.stage_code]
            and other.observed_on < data.observed_on
        ):
            raise HTTPException(
                status_code=409,
                detail="Stage date conflicts with an earlier/later confirmed stage. Edit the dates in order.",
            )

    row = next((item for item in existing if item.stage_code == data.stage_code), None)
    if row is None:
        row = CropStageObservation(crop_cycle_id=cycle.id, stage_code=data.stage_code)
        db.add(row)
    row.observed_on = data.observed_on
    row.notes = data.notes
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Stage was updated concurrently; refresh and retry.") from exc
    db.refresh(row)
    return row


@router.delete(
    "/crop-cycles/{crop_cycle_id}/growth-stages/{stage_code}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_growth_stage(
    crop_cycle_id: UUID,
    stage_code: str,
    db: DBSession,
    current_user: CurrentUser,
) -> None:
    cycle = get_owned_crop_cycle(
        db=db, user_id=current_user.id, crop_cycle_id=crop_cycle_id,
    )
    row = db.scalar(
        select(CropStageObservation).where(
            CropStageObservation.crop_cycle_id == cycle.id,
            CropStageObservation.stage_code == stage_code,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Recorded crop stage not found.")
    db.delete(row)
    db.commit()
