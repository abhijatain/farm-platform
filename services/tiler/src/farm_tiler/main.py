"""Create FastAPI/TiTiler routes for controlled field raster visualization."""

from fastapi import FastAPI, HTTPException, Query, Response, Request
from fastapi.responses import JSONResponse
from hmac import compare_digest
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
from rasterio.errors import RasterioError

from farm_tiler.services.change import (
    read_change_raster,
    render_change_png,
    summarize_change,
)
from farm_tiler.config import settings
from farm_tiler.storage.gcs_path import (
    DatasetPathParams,
)


app = FastAPI(
    title="Farm Platform Tiler",
)

@app.middleware("http")
async def require_internal_api_token(request: Request, call_next):
    """All raster/tile/change routes are API-internal, NEVER browser public.

    Even accidental binding to 0.0.0.0 cannot expose gs:// paths. The local
    /health check remains available for process supervision.
    """
    if request.url.path == "/health":
        return await call_next(request)
    shared = settings.satellite_tiler_shared_token
    if shared is None or not shared.get_secret_value():
        return JSONResponse({"detail": "Private tiler token not configured."}, status_code=503)
    supplied = request.headers.get("X-Farm-Internal-Token", "")
    if not compare_digest(supplied, shared.get_secret_value()):
        return JSONResponse({"detail": "Unauthorized private tiler access."}, status_code=401)
    return await call_next(request)



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
    "/change/summary",
)
def change_summary(
    before: str = Query(
        ...,
        description=(
            "Private Farm Platform gs:// baseline metric COG."
        ),
    ),
    after: str = Query(
        ...,
        description=(
            "Private Farm Platform gs:// later metric COG."
        ),
    ),
    threshold: float = Query(
        ...,
        ge=0.0,
        description=(
            "Absolute pixel change treated as meaningful."
        ),
    ),
):
    try:
        raster = read_change_raster(
            before_uri=before,
            after_uri=after,
        )

        return summarize_change(
            raster=raster,
            threshold=threshold,
        )

    except (
        ValueError,
        RasterioError,
    ) as error:
        raise HTTPException(
            status_code=422,
            detail=str(
                error
            ),
        ) from error


@app.get(
    "/change/preview.png",
)
def change_preview(
    before: str = Query(
        ...,
        description=(
            "Private Farm Platform gs:// baseline metric COG."
        ),
    ),
    after: str = Query(
        ...,
        description=(
            "Private Farm Platform gs:// later metric COG."
        ),
    ),
    max_abs: float = Query(
        ...,
        gt=0.0,
        description=(
            "Symmetric absolute display range for the change raster."
        ),
    ),
) -> Response:
    try:
        raster = read_change_raster(
            before_uri=before,
            after_uri=after,
        )

        payload = render_change_png(
            raster=raster,
            max_abs=max_abs,
        )

        return Response(
            content=payload,
            media_type="image/png",
            headers={
                "Cache-Control":
                    "private, max-age=300",
            },
        )

    except (
        ValueError,
        RasterioError,
    ) as error:
        raise HTTPException(
            status_code=422,
            detail=str(
                error
            ),
        ) from error


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
