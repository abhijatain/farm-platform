from fastapi import APIRouter

from app.api.routes import (
    activities,
    crop_cycles,
    farms,
    fields,
    seasons,
)


api_router = APIRouter()


api_router.include_router(
    farms.router
)

api_router.include_router(
    fields.router
)

api_router.include_router(
    seasons.router
)

api_router.include_router(
    crop_cycles.router
)

api_router.include_router(
    activities.router
)
