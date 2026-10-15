"""Create the FastAPI application and attach middleware and routers."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings


app = FastAPI(
    title="Farm Platform API",
    version="0.1.0",
)


cors_origins = [
    origin.strip()
    for origin in settings.cors_origins.split(",")
    if origin.strip()
]


app.add_middleware(
    CORSMiddleware,

    allow_origins=cors_origins,

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "farm-platform-api",
    }


app.include_router(
    api_router,
    prefix="/api/v1",
)
