"""Authenticated field weather context, with no public arbitrary-coordinate proxy."""
from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DBSession
from app.models.field import Field
from app.schemas.weather import FieldWeatherResponse
from app.services.ownership import get_owned_field
from app.services.weather import WeatherProviderError, load_field_weather, _today


router = APIRouter(tags=["field weather"])


@router.get(
    "/fields/{field_id}/weather",
    response_model=FieldWeatherResponse,
)
def get_field_weather(
    field_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    include_forecast: bool = Query(default=True),
) -> FieldWeatherResponse:
    get_owned_field(
        db=db,
        user_id=current_user.id,
        field_id=field_id,
    )

    # Coordinates come only from the field's persisted polygon.
    point = db.execute(
        select(
            func.ST_Y(func.ST_Centroid(Field.boundary)),
            func.ST_X(func.ST_Centroid(Field.boundary)),
        ).where(Field.id == field_id)
    ).one()
    latitude, longitude = float(point[0]), float(point[1])
    today = _today()
    end = end_date or today
    start = start_date or (end - timedelta(days=90))

    try:
        return load_field_weather(
            field_id=field_id,
            latitude=latitude,
            longitude=longitude,
            start_date=start,
            end_date=end,
            include_forecast=include_forecast,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except WeatherProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
