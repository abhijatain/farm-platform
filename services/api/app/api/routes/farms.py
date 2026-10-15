"""Create and retrieve owner-scoped farms."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession
from app.models.farm import Farm
from app.schemas.farm import FarmCreate, FarmResponse


router = APIRouter(
    prefix="/farms",
    tags=["farms"],
)


@router.post(
    "",
    response_model=FarmResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_farm(
    data: FarmCreate,
    db: DBSession,
    current_user: CurrentUser,
) -> Farm:
    farm = Farm(
        owner_user_id=current_user.id,
        name=data.name,
        location_name=data.location_name,
    )

    db.add(farm)
    db.commit()
    db.refresh(farm)

    return farm


@router.get(
    "",
    response_model=list[FarmResponse],
)
def list_farms(
    db: DBSession,
    current_user: CurrentUser,
) -> list[Farm]:
    statement = (
        select(Farm)
        .where(
            Farm.owner_user_id == current_user.id
        )
        .order_by(Farm.created_at.desc())
    )

    return list(
        db.scalars(statement).all()
    )


@router.get(
    "/{farm_id}",
    response_model=FarmResponse,
)
def get_farm(
    farm_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> Farm:
    farm = db.scalar(
        select(Farm).where(
            Farm.id == farm_id,
            Farm.owner_user_id == current_user.id,
        )
    )

    if farm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farm not found.",
        )

    return farm
