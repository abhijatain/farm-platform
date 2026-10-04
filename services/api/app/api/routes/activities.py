from uuid import UUID

from fastapi import (
    APIRouter,
    HTTPException,
    status,
)
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession
from app.models.activity import Activity
from app.models.crop_cycle import CropCycle
from app.models.season import Season
from app.schemas.activity import (
    ActivityCreate,
    ActivityResponse,
)
from app.schemas.timeline import TimelineItem
from app.services.ownership import (
    get_owned_crop_cycle,
    get_owned_field,
)


router = APIRouter(
    tags=["activities"],
)


@router.post(
    "/fields/{field_id}/activities",
    response_model=ActivityResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_activity(
    field_id: UUID,
    data: ActivityCreate,
    db: DBSession,
    current_user: CurrentUser,
) -> Activity:

    field = get_owned_field(
        db=db,
        user_id=current_user.id,
        field_id=field_id,
    )

    crop_cycle = None

    if data.crop_cycle_id is not None:
        crop_cycle = get_owned_crop_cycle(
            db=db,
            user_id=current_user.id,
            crop_cycle_id=data.crop_cycle_id,
        )

        if crop_cycle.field_id != field.id:
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
                detail=(
                    "The selected crop cycle does not "
                    "belong to this field."
                ),
            )

    activity = Activity(
        field_id=field.id,

        crop_cycle_id=(
            crop_cycle.id
            if crop_cycle is not None
            else None
        ),

        activity_type=data.activity_type,
        occurred_at=data.occurred_at,

        notes=data.notes,
        details=data.details,
    )

    db.add(activity)
    db.commit()
    db.refresh(activity)

    return activity


@router.get(
    "/fields/{field_id}/activities",
    response_model=list[ActivityResponse],
)
def list_field_activities(
    field_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> list[Activity]:

    get_owned_field(
        db=db,
        user_id=current_user.id,
        field_id=field_id,
    )

    activities = db.scalars(
        select(Activity)
        .where(
            Activity.field_id == field_id
        )
        .order_by(
            Activity.occurred_at.desc()
        )
    ).all()

    return list(activities)


@router.get(
    "/fields/{field_id}/timeline",
    response_model=list[TimelineItem],
)
def get_field_timeline(
    field_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> list[TimelineItem]:

    get_owned_field(
        db=db,
        user_id=current_user.id,
        field_id=field_id,
    )

    statement = (
        select(
            Activity,
            CropCycle,
            Season,
        )
        .outerjoin(
            CropCycle,
            CropCycle.id
            == Activity.crop_cycle_id,
        )
        .outerjoin(
            Season,
            Season.id
            == CropCycle.season_id,
        )
        .where(
            Activity.field_id == field_id
        )
        .order_by(
            Activity.occurred_at.desc()
        )
    )

    rows = db.execute(
        statement
    ).all()

    timeline: list[TimelineItem] = []

    for activity, crop_cycle, season in rows:
        timeline.append(
            TimelineItem(
                id=activity.id,

                occurred_at=(
                    activity.occurred_at
                ),

                activity_type=(
                    activity.activity_type
                ),

                notes=activity.notes,
                details=activity.details,

                crop_cycle_id=(
                    crop_cycle.id
                    if crop_cycle
                    else None
                ),

                crop_name=(
                    crop_cycle.crop_name
                    if crop_cycle
                    else None
                ),

                variety=(
                    crop_cycle.variety
                    if crop_cycle
                    else None
                ),

                season_id=(
                    season.id
                    if season
                    else None
                ),

                season_name=(
                    season.name
                    if season
                    else None
                ),
            )
        )

    return timeline
