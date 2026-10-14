# Farm Tiler

TiTiler-based raster service used by the web application to render canonical
private GCS COGs.

## Setup

```bash
cp .env.example .env
uv sync
uv run uvicorn farm_tiler.main:app --host 0.0.0.0 --port 8081 --reload
```

Set `GCS_BUCKET_NAME` and provide Google credentials locally when Application
Default Credentials are not already configured.

The web application must set `VITE_TILER_URL` explicitly.
