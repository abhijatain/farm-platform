"""Mount FastAPI route groups in one stable versioned router."""

from fastapi import APIRouter

from app.api.routes import (
    activities,
    auth,
    crop_cycles,
    crop_growth,
    farms,
    fields,
    field_intelligence,
    seasonal_zones,
    weather,
    media,
    satellite_observations,
    private_satellite_previews,
    radar_screening,
    whatsapp_webhook,
    whatsapp_link,
    seasons,
)

api_router = APIRouter()


api_router.include_router(auth.router)

api_router.include_router(farms.router)

api_router.include_router(fields.router)
api_router.include_router(weather.router)

api_router.include_router(seasons.router)

api_router.include_router(crop_cycles.router)
api_router.include_router(crop_growth.router)

api_router.include_router(activities.router)

api_router.include_router(media.router)

api_router.include_router(satellite_observations.router)
api_router.include_router(field_intelligence.router)
api_router.include_router(seasonal_zones.router)
api_router.include_router(private_satellite_previews.router)

api_router.include_router(radar_screening.router)

# Meta webhooks use their own signature, never Firebase bearer authentication.
api_router.include_router(whatsapp_webhook.router)
api_router.include_router(whatsapp_link.router)
