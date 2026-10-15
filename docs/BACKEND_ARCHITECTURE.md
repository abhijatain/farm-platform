# Backend architecture and contribution guide

The repository contains three deployable backend services with deliberately
different responsibilities. All frontend code remains untouched by this
refactor, and preserve their HTTP and database contracts. Obsolete Python import paths
and module command entry points have intentionally been retired.

## Repository layout

```text
services/
  api/
    app/
      api/
        deps.py              # Authenticated user + request-scoped DB session
        routes/              # FastAPI HTTP adapter, authorization and validation
      domains/
        activities/          # Observation comparisons around farmer activities
        crops/               # Crop phenology rules
        media/               # Upload validation, derivatives, signed retrieval
        satellite/           # Optical/radar analysis, timelines, ingestion
      models/                # SQLAlchemy ORM and canonical PostGIS tables
      schemas/               # Pydantic HTTP request and response contracts
      services/              # Active weather, crop growth and ownership
      core/                  # Runtime configuration and Firebase integration
      db/                    # Engine, sessions, model registration
      storage/               # Private GCS objects, paths and recovery manifests
      utils/
    alembic/                 # Existing immutable migration history
    scripts/                 # Administrative CLI and diagnostics
    tests/
  satellite-worker/
    src/satellite_worker/
      sources/
        sentinel1/pipeline.py
        sentinel2/           # Bands, grid, indices, reflectance, pipeline
        landsat/pipeline.py
        stac.py              # Satellite catalog queries
      processing/
        anomaly.py           # Field-relative spatial anomalies
        anomaly_rules.py
        raster.py            # Shared cross-sensor COG/raster utilities
      ingestion/
        worker.py            # Durable job loop and processor invocation
      persistence/
        connection.py        # Shared SQLAlchemy engine
        scenes.py            # Scene and metric data
        jobs.py              # Queued, retryable ingestion jobs
      storage/
        gcs.py               # Private GCS access
        rasters.py           # Upload, publish, materialize
        context.py           # Farm and field storage context
        layout.py            # Versioned canonical object keys
        manifests.py         # Recovery information
      cli/                   # Batch/backfill/manifest maintenance commands
      config.py
    tests/
  tiler/
    src/farm_tiler/
      main.py                # HTTP app and raster endpoints
      services/change.py     # Pixel difference raster operations
      storage/gcs_path.py    # Validated private GCS inputs
      config.py
    tests/
tools/
  check_backend_docs.py      # AST-enforced module docstrings
docs/
  BACKEND_ARCHITECTURE.md
```

## Where to add backend code

| Responsibility | Place it | Do not place it |
|---|---|---|
| HTTP status, request validation, per-user ownership | API api/routes | Worker/tiler/domain algebra |
| Crop growth or agronomic calculations | API domains/crops or standalone tested growth services | HTTP route handlers |
| Satellite field reports and comparisons | API domains/satellite | Generic ORM models |
| Ingestion rate limits, retries, job lifecycle | Worker ingestion and persistence/jobs | Individual spectral formulas |
| Sentinel-1 or Landsat algorithms | Worker sources/sentinel1 or sources/landsat | Sentinel-2 helpers |
| Optical bands, masks and index formulae | Worker sources/sentinel2 | Geospatial REST layer |
| Raster statistics, anomaly geometry and raster alignment | Worker processing | Farm ownership routes |
| Private cloud paths and manifests | Each backend service's storage package | Frontend-visible secrets |
| Raster tiles and map change previews | Tiler service | PostgreSQL query adapters |
| DB revisions | services/api/alembic | Worker code |

## Dependency rules

- API request adapters depend on domain services, ORM models and validated
  schemas. Domain services should not import API route modules or FastAPI
  request dependency aliases.
- Satellite pipelines depend on shared processing, persistence, and storage;
  none of those lower layers may depend on sensor pipeline modules.
- Storage keys are **not renamed** in this refactor. GCS recovery manifests
  remain stable and are not a replacement for PostgreSQL canonical records.
- All external identifiers are verified for scope/ownership at the API
  boundary. Reusable utilities do not authorize themselves by trusting a
  field ID sent over the network.
- Keep sensor provenance, native resolution and pixel-quality metadata; do
  not interpret NDVI, NDMI, SAR or ET0 as automatic disease, yield or
  root-zone moisture diagnoses.

## One canonical implementation per component

Old forwarding modules are **removed**. Code and tests import the implementation
from its domain, sensor, storage or persistence package directly.

| Component | Supported module |
|---|---|
| API satellite analysis | `app.domains.satellite.change`, `.timeline`, `.trends`, `.radar_screening` |
| API activity, crop and media | `app.domains.activities.satellite`, `app.domains.crops.phenology`, `app.domains.media.*` |
| Sensor pipelines | `satellite_worker.sources.sentinel1.pipeline`, `.sentinel2.pipeline`, `.landsat.pipeline` |
| Shared processing | `satellite_worker.processing.*` |
| Worker persistence | `satellite_worker.persistence.*` |
| Worker object storage | `satellite_worker.storage.*` |
| Job runner and manual operations | `satellite_worker.ingestion.worker`, `satellite_worker.cli.*` |
| Tiler | `farm_tiler.services.change`, `farm_tiler.storage.gcs_path` |

The installed `satellite-ingestion-worker` console command is supported: it
directly calls `satellite_worker.ingestion.worker:main`, not a forwarding file.

```bash
uv run satellite-ingestion-worker --once
uv run python -m satellite_worker.sources.sentinel2.pipeline --help
uv run python -m satellite_worker.sources.sentinel1.pipeline --help
uv run python -m satellite_worker.sources.landsat.pipeline --help
uv run python -m satellite_worker.cli.process_all_fields --help
uv run python -m satellite_worker.cli.backfill_metric_anomalies --help
uv run python -m satellite_worker.cli.refresh_storage_manifests --help
```

**External deployment change:** update any crontab, Cloud Run Job, Docker
command or standalone script that used a former top-level satellite worker
module. This is a deliberate Python-import/CLI path breaking change, **not**
a change to the HTTP API, stored data, or GCS object paths.

## Operational safeguards and conventions

- Database: SQLAlchemy/PostGIS is the canonical farm data store. Do not alter
  existing SQLAlchemy models, Alembic heads or SQL query semantics merely
  because files move.
- Sensors: radar comparison must honor ascending/descending and relative
  orbit. Optical trends must respect field pixel quality and cloud masking.
- Weather: distinguish historical reanalysis, archived model fallback,
  recent models and forecasts; missing days are not zero rainfall.
- Tasks: ingestion retry/deduplication and partial-source success are
  historical behavior and must remain stable.
- Privacy: never log raw bearer tokens, signed media URLs or farm secrets.
- Comment style: every Python module has a concise purpose docstring. Add
  comments for **why** rules, failure-handling and temporal assumptions
  matter, not a comment on every assignment.
- Tests: protect public route behavior, canonical CLI commands and
  forbidden legacy dependencies. Run lint/build before merging.

## Verification

From the repository root:
```bash
python tools/check_backend_docs.py
python tools/check_backend_architecture.py
```

API:
```bash
cd services/api
uv sync --frozen
uv run alembic current --check-heads
uv run --with pytest python -m pytest -q tests
uv run python -m compileall -q app scripts
```

Worker:
```bash
cd services/satellite-worker
uv sync --frozen
uv run --with pytest pytest -q tests
```

Tiler:
```bash
cd services/tiler
uv sync --frozen
uv run --with pytest pytest -q tests
```

CI additionally tests migrations on **fresh PostGIS**, application imports
and the unchanged web build. Refactoring does not require a DB migration.

### Still-valid top-level services

`app.services.crop_growth`, `app.services.weather`, and
`app.services.ownership` are the actual implementations—not compatibility
wrappers. Public HTTP routers, Pydantic schemas and SQLAlchemy models also
remain in their appropriate stable packages.
