# Farm Platform

Digital field intelligence and agricultural record system for farms, fields,
crop cycles, activities, media, yield, and multi-source satellite analysis.

## Product plan and current capabilities

- [Feature inventory: already implemented, foundations, and open PRs](docs/FEATURE_INVENTORY.md)
- [Prioritized non-drone TODO and detailed rollout sequence](TODO.md)
- [WhatsApp-first farmer interface: multilingual chat, voice, reports, onboarding and secure Meta integration](docs/WHATSAPP_FIRST_PRODUCT.md)

Feature importance/feasibility scores in these documents are planning judgments,
not scientific accuracy guarantees. Drone-dependent features are deferred.

For backend contributors, see [the organized backend package map and compatibility rules](docs/BACKEND_ARCHITECTURE.md).

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


## Field weather context and radar presentation

The Satellite workspace now shows a **primary same-orbit Radar RVI trend**,
with VV, VH, VV/VH and the radar pass table under an expandable technical
section. Radar increases/decreases are *not* interpreted as crop health.

Weather is fetched on demand through the authenticated field endpoint:

    GET /api/v1/fields/{field_id}/weather?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&include_forecast=true

- Server derives coordinates from the owned field polygon centroid (PostGIS);
  clients cannot use this endpoint to query arbitrary coordinates.
- Provider is [Open-Meteo](https://open-meteo.com/). Up to 367 days per
  request, with past historical reanalysis (through eight days ago), recent
  modeled weather (last seven days), and the next six forecast days.
- Daily values: precipitation (mm), minimum/maximum 2-m air temperature (°C),
  mean relative humidity (%), max wind speed at 10 m (km/h), reference ET₀
  (mm), and WMO weather code. Dates follow the field's model timezone.
- Missing readings remain null, never false zero precipitation.
- Weather errors are isolated from satellite-trend loading.
- Independent bounded in-process cache: 6 h for archive, 15 min for
  recent/forecast; multiple API instances each maintain their own cache.
- No weather data is written to PostgreSQL and **no migration is needed**
  for this phase. Later persistent weather/alerts can use a normalized
  model with provider/source and run-time provenance.

**Licensing**: Open-Meteo's no-key public service is for non-commercial
development use. For deployment in commercial production, configure the
server-side WEATHER_API_KEY with a valid commercial subscription; the API
deliberately refuses unauthenticated free-tier access in
ENVIRONMENT=production. The key must **never** be exposed via a VITE_
environment variable.

Weather reanalysis and recent forecasts are modeled grid-cell estimates,
not sensor readings at the farm. Rain near a radar pass is context only, and
crop-stage-aware SAR anomaly detection remains disabled.


## Crop development and growth-stage tracking

An active crop cycle now includes a crop-development diary above the
satellite graphs. Each farmer-confirmed stage transition is saved in the
crop_stage_observations table, scoped to the authenticated crop-cycle owner.
Markers are overlaid on optical and same-orbit Radar RVI charts.

The API offers:

    GET    /api/v1/crop-cycles/{id}/growth-stages
    PUT    /api/v1/crop-cycles/{id}/growth-stages
    DELETE /api/v1/crop-cycles/{id}/growth-stages/{stage_code}

PUT accepts stage_code, observed_on (YYYY-MM-DD) and optional notes.
Each stage can be corrected without adding duplicate records; dates are
checked against crop planting/start, today, harvest and chronological
stage order. Generic manual-only stages are available for crops without
a supported model.

Wheat, rice and maize have **broad provisional day-after-planting milestone
templates**, version 2026-10-v1. They are explanatory estimates only, not
region/variety-calibrated recommendations. No automatic stage is generated
when the planting date is missing, and generic/unrecognized crops receive
no speculative growth predictions.

Accumulated growing-degree days (GDD) are displayed independently of
milestone prediction. GDD uses daily model/reanalysis temperatures from
Open-Meteo at the field centroid, and is suppressed if *any* planting-to-date
temperature day is missing. Available crop base temperatures: wheat 0 °C,
rice 10 °C, maize 10 °C. These simplify development context, do not
account for thermal upper limits, photoperiod, cultivar, vernalization or
local management, and should not drive agronomic alerts without validation.

Run the **new Alembic migration** before deploying the updated API:

    cd services/api
    uv run alembic upgrade head

Crop growth stages are context for later radar/crop-specific anomalies;
SAR anomaly classification remains intentionally disabled.


### Weather provider troubleshooting

In development, a 503 from the field-weather API means no source returned
usable data; it does not mean the crop has no rainfall. The server now logs
sanitized provider diagnostics (source + HTTP status/reason or network failure)
without logging API keys. Source labels:
- "historical": Open-Meteo reanalysis (preferred).
- "historical_forecast": archived model-run fallback from 2022 onward.
- "recent_model": recent weather-model estimates.
- "forecast": future weather-model estimates (never an observation).

The forecast API uses supported daily variables and computes mean relative
humidity from hourly data, rather than requesting a nonportable daily
humidity field. Run the local diagnostic CLI from services/api:

    uv run python scripts/check_weather_provider.py --latitude 30.7 --longitude 76.7 --start 2026-06-18 --end 2026-10-08

These are example coordinates. The CLI prints HTTP errors and transport
failures without displaying API keys. No database migration is required
for this weather-provider correction.

**Channel status:** WhatsApp is a high-priority planned farmer interface, not yet implemented. Roadmap items T61–T80 cover Meta Cloud API, verified farm linking, consent, native-language onboarding, activity and media capture, reports, voice and templates. The existing web remains the advanced mapping/analysis interface.
