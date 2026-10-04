from fastapi import FastAPI

from app.api.router import api_router


app = FastAPI(
    title="Farm Platform API",
    version="0.1.0",
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
