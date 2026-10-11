from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from titiler.core.errors import DEFAULT_STATUS_CODES, add_exception_handlers
from titiler.core.factory import TilerFactory

app = FastAPI(
    title="Farm Platform Tiler",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
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
    }
