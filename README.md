# Farm Platform

Digital field intelligence and agricultural record system for farms, fields,
crop cycles, activities, media, yield, and multi-source satellite analysis.

## Stack

- Web: React 19 + Vite + TypeScript
- Maps: MapLibre + MapTiler
- Authentication: Firebase phone authentication
- API: FastAPI + SQLAlchemy
- Database: PostgreSQL + PostGIS
- Migrations: Alembic
- Object storage: private Google Cloud Storage
- Satellite processing: Python + Sentinel-2 + Sentinel-1 RTC + Landsat + Rasterio + rio-cogeo
- Raster serving: TiTiler
- Python environment management: uv

## Repository layout

```text
apps/
  web/                  React/Vite web application

services/
  api/                  FastAPI API and Alembic migrations
  satellite-worker/     Optical/radar/thermal processing and recovery manifests
  tiler/                TiTiler service for private GCS COGs
```

## Satellite data model

Scene-level information lives in `satellite_observations`.

Each calculated index is stored in `satellite_metrics`, including its
statistics, coverage information, processing metadata, and canonical GCS COG
URI. Relative anomaly zones live in `satellite_anomalies`.

Older observations may contain only NDVI because they were generated before
the multi-metric pipeline existed. Those rows are valid historical data and
are intentionally not backfilled.

## Object storage

Production objects live in private GCS. Canonical objects are arranged as:

```text
users/{user_id}/
  user.json
  farms/{farm-slug}__{farm_id}/
    farm.json
    fields/{field-slug}__{field_id}/
      field.json
      dates/YYYY/MM/DD/
        media/{media_id}/...
        satellite/{observation_id}/...
```

Recovery manifests are stored alongside object data so the hierarchy remains
understandable even if the operational PostgreSQL database is unavailable.

## Run the API

```bash
cd services/api
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Run the web app

```bash
cd apps/web
cp .env.example .env
pnpm install
pnpm dev
```

The web app requires `VITE_API_URL`, `VITE_TILER_URL`,
`VITE_MAPTILER_KEY`, and Firebase web configuration.

## Run the tiler

```bash
cd services/tiler
cp .env.example .env
uv sync
uv run uvicorn farm_tiler.main:app --host 0.0.0.0 --port 8081 --reload
```

## Automatic multi-source satellite ingestion

After the database migration is applied, field creation automatically queues a
90-day backfill. One ingestion job processes:

- Sentinel-2 optical metrics: NDVI, NDRE, NDMI, GNDVI, EVI2, NDWI, SAVI,
  MSAVI, BSI, NDTI, CCCI, RECI, MCARI.
- Sentinel-1 RTC all-weather radar: VV dB, VH dB, VV/VH ratio, dual-pol RVI.
- Landsat Collection 2 thermal: land-surface temperature in °C.

Run the ingestion worker as a long-lived service:

```bash
cd services/satellite-worker
cp .env.example .env
uv sync
uv run satellite-ingestion-worker
```

The flow is:

```text
field created
  -> initial backfill job (default 90 days)
  -> ingestion worker claims job
  -> Sentinel-2 discovery (Earth Search)
  -> Sentinel-1 RTC + Landsat discovery (Planetary Computer)
  -> metric COG processing
  -> private GCS publish
  -> PostgreSQL observations/metrics/anomalies
  -> recovery manifest
  -> web UI detects the result automatically
```

The worker also bootstraps existing fields with zero metric data and queues
idempotent incremental refresh jobs. Existing historical scenes with metrics,
including NDVI-only observations, are preserved and skipped by automation.

Cloud-covered optical scenes are stored as handled observations with cloud/
coverage metadata and no fabricated optical metrics. Sentinel-1 is a separate
radar source and remains usable through clouds; when a radar acquisition exists
near a cloudy optical date, its radar metrics are stored in its own observation.

For a scheduled/ephemeral worker instead of a long-lived process:

```bash
uv run satellite-ingestion-worker --once
```

Manual field processing remains available:

```bash
uv run python -m satellite_worker.process_field \
  --field-id <FIELD_UUID> \
  --start 2026-10-01 \
  --end 2026-10-14
```

A processing command exits non-zero when any selected scene fails. Batch
processing likewise exits non-zero if a field fails.

## Maintenance

Inspect the complete database schema and integrity state:

```bash
cd services/api
uv run python scripts/dump_db_schema.py
```

Remove abandoned pending/failed media uploads older than 24 hours:

```bash
cd services/api
uv run python scripts/cleanup_stale_media_uploads.py --dry-run
uv run python scripts/cleanup_stale_media_uploads.py
```

## Tests and CI

GitHub Actions validates:

- a migration from an empty PostgreSQL + PostGIS database;
- `alembic check`;
- API schema regression tests;
- the historical NDVI-only observation contract;
- Sentinel-2 optical metric formula tests;
- Sentinel-1 radar formula tests;
- Landsat LST scale/QA tests;
- field-level cloud coverage tests;
- Python compilation;
- the TypeScript/Vite build;
- web linting.

Local API tests:

```bash
cd services/api
uv run --with pytest python -m pytest -q tests
```

Local worker tests:

```bash
cd services/satellite-worker
uv run --with pytest pytest -q tests
```

Local web checks:

```bash
cd apps/web
pnpm build
pnpm lint
```
