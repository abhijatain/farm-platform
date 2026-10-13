
from fastapi import FastAPI
from fastapi.middleware.cors import (
    CORSMiddleware,
)
from titiler.core.errors import (
    DEFAULT_STATUS_CODES,
    add_exception_handlers,
)
from titiler.core.factory import (
    TilerFactory,
)

from farm_tiler.config import settings
from farm_tiler.gcs_path import (
    DatasetPathParams,
)


app = FastAPI(
    title="Farm Platform Tiler",
)


origins = [
    value.strip()
    for value
    in settings
    .cors_origins
    .split(",")
    if value.strip()
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=[
        "GET",
    ],
    allow_headers=[
        "*",
    ],
)


cog = TilerFactory(
    router_prefix="/cog",
    add_preview=True,
    path_dependency=(
        DatasetPathParams
    ),
)


app.include_router(
    cog.router,
    prefix="/cog",
    tags=[
        "COG",
    ],
)


add_exception_handlers(
    app,
    DEFAULT_STATUS_CODES,
)


@app.get(
    "/health",
)
def health():
    return {
        "status": "ok",
        "storage": "private-gcs",
        "bucket": (
            settings.gcs_bucket_name
        ),
    }
