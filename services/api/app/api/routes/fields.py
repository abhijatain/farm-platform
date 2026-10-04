from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from geoalchemy2 import Geography
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Polygon, mapping, shape
from shapely.validation import explain_validity
from sqlalchemy import cast, func, select

from app.api.deps import CurrentUser, DBSession
from app.models.farm import Farm
from app.models.field import Field as FarmField
from app.schemas.field import (
    FieldCreate,
    FieldResponse,
    PolygonGeometry,
)


router = APIRouter(
    tags=["fields"],
)


def get_owned_farm(
    farm_id: UUID,
    user_id: UUID,
    db: DBSession,
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
    field_id: UUID,
    user_id: UUID,
    db: DBSession,
) -> FarmField:
    field = db.scalar(
        select(FarmField)
        .join(
            Farm,
            Farm.id == FarmField.farm_id,
        )
        .where(
            FarmField.id == field_id,
            Farm.owner_user_id == user_id,
        )
    )

    if field is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Field not found.",
        )

    return field


def calculate_area_square_metres(
    field: FarmField,
    db: DBSession,
) -> float:
    """
    Geometry is stored as EPSG:4326.

    Casting to PostGIS geography makes ST_Area return
    square metres on the earth's surface.
    """

    area = db.scalar(
        select(
            func.ST_Area(
                cast(
                    FarmField.boundary,
                    Geography(
                        geometry_type="POLYGON",
                        srid=4326,
                    ),
                )
            )
        ).where(
            FarmField.id == field.id
        )
    )

    return float(area or 0.0)


def field_to_response(
    field: FarmField,
    db: DBSession,
) -> FieldResponse:
    shapely_geometry = to_shape(
        field.boundary
    )

    geojson = PolygonGeometry.model_validate(
        mapping(shapely_geometry)
    )

    square_metres = calculate_area_square_metres(
        field,
        db,
    )

    return FieldResponse(
        id=field.id,
        farm_id=field.farm_id,
        name=field.name,
        boundary=geojson,

        area_square_metres=round(
            square_metres,
            2,
        ),

        area_hectares=round(
            square_metres / 10_000,
            4,
        ),

        area_acres=round(
            square_metres / 4046.8564224,
            4,
        ),

        created_at=field.created_at,
        updated_at=field.updated_at,
    )


@router.post(
    "/farms/{farm_id}/fields",
    response_model=FieldResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_field(
    farm_id: UUID,
    data: FieldCreate,
    db: DBSession,
    current_user: CurrentUser,
) -> FieldResponse:

    get_owned_farm(
        farm_id=farm_id,
        user_id=current_user.id,
        db=db,
    )

    geometry_data = data.boundary.model_dump()

    polygon = shape(
        geometry_data
    )

    if not isinstance(polygon, Polygon):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Field boundary must be a Polygon.",
        )

    if polygon.is_empty:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Field boundary cannot be empty.",
        )

    if not polygon.is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Invalid field boundary.",
                "reason": explain_validity(polygon),
            },
        )

    field = FarmField(
        farm_id=farm_id,
        name=data.name,
        boundary=from_shape(
            polygon,
            srid=4326,
        ),
    )

    db.add(field)
    db.commit()
    db.refresh(field)

    return field_to_response(
        field,
        db,
    )


@router.get(
    "/farms/{farm_id}/fields",
    response_model=list[FieldResponse],
)
def list_fields(
    farm_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> list[FieldResponse]:

    get_owned_farm(
        farm_id=farm_id,
        user_id=current_user.id,
        db=db,
    )

    fields = db.scalars(
        select(FarmField)
        .where(
            FarmField.farm_id == farm_id
        )
        .order_by(
            FarmField.created_at.desc()
        )
    ).all()

    return [
        field_to_response(field, db)
        for field in fields
    ]


@router.get(
    "/fields/{field_id}",
    response_model=FieldResponse,
)
def get_field(
    field_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> FieldResponse:

    field = get_owned_field(
        field_id=field_id,
        user_id=current_user.id,
        db=db,
    )

    return field_to_response(
        field,
        db,
    )
