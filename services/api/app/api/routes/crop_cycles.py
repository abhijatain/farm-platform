"""Manage planted crop cycles and measured harvest outcomes."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession
from app.models.activity import Activity
from app.models.crop_cycle import CropCycle
from app.schemas.crop_cycle import (
    CropCycleCreate,
    CropCyclePlanUpdate,
    CropCycleResponse,
    HarvestCropCycleRequest,
    HarvestCropCycleResponse,
)
from app.services.ownership import (
    get_owned_crop_cycle,
    get_owned_field,
    get_owned_season,
)

router = APIRouter(
    tags=["crop cycles"],
)


@router.post(
    "/seasons/{season_id}/crop-cycles",
    response_model=CropCycleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_crop_cycle(
    season_id: UUID,
    data: CropCycleCreate,
    db: DBSession,
    current_user: CurrentUser,
) -> CropCycle:

    season = get_owned_season(
        db=db,
        user_id=current_user.id,
        season_id=season_id,
    )

    field = get_owned_field(
        db=db,
        user_id=current_user.id,
        field_id=data.field_id,
    )

    if field.farm_id != season.farm_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=("The field and season must " "belong to the same farm."),
        )

    crop_cycle = CropCycle(
        season_id=season.id,
        field_id=field.id,
        crop_name=data.crop_name,
        variety=data.variety,
        status="active",
        started_on=data.started_on,
        planted_on=data.planted_on,
        expected_harvest_on=(data.expected_harvest_on),
        harvested_on=None,
        notes=data.notes,
    )

    db.add(crop_cycle)
    db.commit()
    db.refresh(crop_cycle)

    return crop_cycle


@router.get(
    "/seasons/{season_id}/crop-cycles",
    response_model=list[CropCycleResponse],
)
def list_season_crop_cycles(
    season_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> list[CropCycle]:

    get_owned_season(
        db=db,
        user_id=current_user.id,
        season_id=season_id,
    )

    crop_cycles = db.scalars(
        select(CropCycle)
        .where(CropCycle.season_id == season_id)
        .order_by(CropCycle.started_on.desc())
    ).all()

    return list(crop_cycles)


@router.get(
    "/fields/{field_id}/crop-cycles",
    response_model=list[CropCycleResponse],
)
def list_field_crop_cycles(
    field_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> list[CropCycle]:

    get_owned_field(
        db=db,
        user_id=current_user.id,
        field_id=field_id,
    )

    crop_cycles = db.scalars(
        select(CropCycle)
        .where(CropCycle.field_id == field_id)
        .order_by(CropCycle.started_on.desc())
    ).all()

    return list(crop_cycles)


@router.get(
    "/crop-cycles/{crop_cycle_id}",
    response_model=CropCycleResponse,
)
def get_crop_cycle(
    crop_cycle_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> CropCycle:

    return get_owned_crop_cycle(
        db=db,
        user_id=current_user.id,
        crop_cycle_id=crop_cycle_id,
    )


@router.patch(
    "/crop-cycles/{crop_cycle_id}/plan",
    response_model=CropCycleResponse,
)
def update_crop_cycle_plan(
    crop_cycle_id: UUID,
    data: CropCyclePlanUpdate,
    db: DBSession,
    current_user: CurrentUser,
) -> CropCycle:
    """Correct sowing date or expected harvest; don't overwrite harvest history."""
    cycle = get_owned_crop_cycle(
        db=db, user_id=current_user.id, crop_cycle_id=crop_cycle_id,
    )
    if cycle.status != "active" or cycle.harvested_on is not None:
        raise HTTPException(status_code=409, detail="Completed crop cycles cannot be rescheduled.")
    planted = data.planted_on if "planted_on" in data.model_fields_set else cycle.planted_on
    expected = (
        data.expected_harvest_on
        if "expected_harvest_on" in data.model_fields_set
        else cycle.expected_harvest_on
    )
    if planted is not None and planted < cycle.started_on:
        raise HTTPException(status_code=422, detail="Planting cannot precede field preparation.")
    if expected is not None and expected < (planted or cycle.started_on):
        raise HTTPException(status_code=422, detail="Expected harvest must follow planting/start.")
    cycle.planted_on = planted
    cycle.expected_harvest_on = expected
    db.commit()
    db.refresh(cycle)
    return cycle


@router.post(
    "/crop-cycles/{crop_cycle_id}/harvest",
    response_model=HarvestCropCycleResponse,
)
def harvest_crop_cycle(
    crop_cycle_id: UUID,
    data: HarvestCropCycleRequest,
    db: DBSession,
    current_user: CurrentUser,
) -> HarvestCropCycleResponse:

    crop_cycle = get_owned_crop_cycle(
        db=db,
        user_id=current_user.id,
        crop_cycle_id=crop_cycle_id,
    )

    if crop_cycle.harvested_on is not None or crop_cycle.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=("This crop cycle has already " "been harvested."),
        )

    reference_date = crop_cycle.planted_on or crop_cycle.started_on

    if data.harvested_at.date() < reference_date:
        raise HTTPException(
            status_code=(status.HTTP_422_UNPROCESSABLE_ENTITY),
            detail=("Harvest date cannot be before " "the crop planting/start date."),
        )

    yield_per_acre = data.yield_kg / data.harvested_area_acres

    estimated_value: float | None = None

    if data.selling_price_per_kg is not None:
        estimated_value = data.yield_kg * data.selling_price_per_kg

    crop_cycle.harvested_on = data.harvested_at.date()

    crop_cycle.status = "completed"

    crop_cycle.yield_kg = data.yield_kg

    crop_cycle.harvested_area_acres = data.harvested_area_acres

    crop_cycle.moisture_percent = data.moisture_percent

    crop_cycle.quality_grade = data.quality_grade

    crop_cycle.selling_price_per_kg = data.selling_price_per_kg

    crop_cycle.harvest_notes = data.notes

    harvest_activity = Activity(
        field_id=crop_cycle.field_id,
        crop_cycle_id=crop_cycle.id,
        activity_type="harvest",
        occurred_at=data.harvested_at,
        notes=data.notes,
        details={
            "yield_kg": data.yield_kg,
            "harvested_area_acres": data.harvested_area_acres,
            "yield_kg_per_acre": round(
                yield_per_acre,
                2,
            ),
            "moisture_percent": data.moisture_percent,
            "quality_grade": data.quality_grade,
            "selling_price_per_kg": data.selling_price_per_kg,
            "estimated_value": (
                round(
                    estimated_value,
                    2,
                )
                if estimated_value is not None
                else None
            ),
        },
    )

    db.add(harvest_activity)

    db.commit()

    db.refresh(crop_cycle)

    return HarvestCropCycleResponse(
        crop_cycle_id=(crop_cycle.id),
        status=(crop_cycle.status),
        harvested_on=(crop_cycle.harvested_on),
        yield_kg=(crop_cycle.yield_kg),
        harvested_area_acres=(crop_cycle.harvested_area_acres),
        yield_kg_per_acre=(
            round(
                yield_per_acre,
                2,
            )
        ),
        moisture_percent=(crop_cycle.moisture_percent),
        quality_grade=(crop_cycle.quality_grade),
        selling_price_per_kg=(crop_cycle.selling_price_per_kg),
        estimated_value=(
            round(
                estimated_value,
                2,
            )
            if estimated_value is not None
            else None
        ),
    )
