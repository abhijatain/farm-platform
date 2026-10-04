from uuid import UUID

from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession
from app.models.season import Season
from app.schemas.season import (
    SeasonCreate,
    SeasonResponse,
)
from app.services.ownership import (
    get_owned_farm,
    get_owned_season,
)


router = APIRouter(
    tags=["seasons"],
)


@router.post(
    "/farms/{farm_id}/seasons",
    response_model=SeasonResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_season(
    farm_id: UUID,
    data: SeasonCreate,
    db: DBSession,
    current_user: CurrentUser,
) -> Season:

    get_owned_farm(
        db=db,
        user_id=current_user.id,
        farm_id=farm_id,
    )

    season = Season(
        farm_id=farm_id,
        name=data.name,
        season_type=data.season_type,
        status="active",
        started_on=data.started_on,
        ended_on=data.ended_on,
    )

    db.add(season)
    db.commit()
    db.refresh(season)

    return season


@router.get(
    "/farms/{farm_id}/seasons",
    response_model=list[SeasonResponse],
)
def list_seasons(
    farm_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> list[Season]:

    get_owned_farm(
        db=db,
        user_id=current_user.id,
        farm_id=farm_id,
    )

    seasons = db.scalars(
        select(Season)
        .where(
            Season.farm_id == farm_id
        )
        .order_by(
            Season.started_on.desc()
        )
    ).all()

    return list(seasons)


@router.get(
    "/seasons/{season_id}",
    response_model=SeasonResponse,
)
def get_season(
    season_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> Season:

    return get_owned_season(
        db=db,
        user_id=current_user.id,
        season_id=season_id,
    )
