from uuid import UUID

from fastapi import (
    APIRouter,
    HTTPException,
    status,
)
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession
from app.models.crop_cycle import CropCycle
from app.schemas.crop_cycle import (
    CropCycleCreate,
    CropCycleResponse,
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
            detail=(
                "The field and season must "
                "belong to the same farm."
            ),
        )

    crop_cycle = CropCycle(
        season_id=season.id,
        field_id=field.id,

        crop_name=data.crop_name,
        variety=data.variety,

        status="active",

        started_on=data.started_on,
        planted_on=data.planted_on,

        expected_harvest_on=(
            data.expected_harvest_on
        ),

        harvested_on=data.harvested_on,

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
        .where(
            CropCycle.season_id == season_id
        )
        .order_by(
            CropCycle.started_on.desc()
        )
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
        .where(
            CropCycle.field_id == field_id
        )
        .order_by(
            CropCycle.started_on.desc()
        )
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
