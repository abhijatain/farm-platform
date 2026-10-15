# Backend architecture

**Scope:** FastAPI API, satellite ingestion worker, TiTiler. The React frontend is intentionally unchanged by this refactor.

## Directory ownership

| Directory | Responsibility | Avoid |
|---|---|---|
| services/api/app/api/routes | HTTP request/response validation, authorization, status codes | Long geospatial calculations and upload policy |
| services/api/app/services | Reusable use cases, metric comparisons, weather, crop growth | Importing FastAPI routes or mutable browser state |
| services/api/app/models | SQLAlchemy persistence models and relations | API presentation logic |
| services/api/app/schemas | Pydantic contracts and validation | Network or database I/O |
| services/api/app/core + db | Runtime configuration, Firebase identity and pooled sessions | Crop-health interpretation |
| services/api/app/storage | Private GCS access, stable cloud layouts, manifests | Unrestricted public storage URLs |
| services/api/alembic/versions | Ordered immutable schema migration history | Editing revisions already applied in production |
| services/api/scripts | Explicit maintenance and diagnostics commands | Destructive work at import time |
| services/satellite-worker/src/satellite_worker/persistence/scenes.py | Field geometry and scene/metric/anomaly reads and writes | Job queue policy |
| services/satellite-worker/src/satellite_worker/persistence/jobs.py | Satellite ingestion queue, retry/claim/recovery | Raster processing |
| services/satellite-worker/src/satellite_worker/persistence/connection.py | One shared SQLAlchemy engine | Duplicated connection pools |
| services/satellite-worker/src/satellite_worker/sentinel2 | Spectral-band metadata, reflectance, masks, index calculations | API route response schemas |
| services/satellite-worker/src/satellite_worker/process_* | Source-specific scene orchestration and cloud publishing | Other sensors' index formulas |
| services/tiler/src/farm_tiler | Controlled private COG rendering and change raster previews | Arbitrary unrestricted cloud reads |

## What was decoupled

- The field activity route delegates its metric selection, scalar before/after comparison and spatial anomaly overlap queries to app.services.activity_satellite.
- The media routes use app.services.media_uploads for permitted content types, size limits, signed link/response construction, and storage-manifest helpers.
- The satellite worker now separates scenes and ingestion jobs into persistence repositories. The satellite_worker.db module reexports functions for backwards compatibility; new code should import directly from persistence.scenes and persistence.jobs.

## Invariants worth documenting

- **One system of record:** field/crop/activity data lives in PostgreSQL/PostGIS. GCS stores durable rasters/media and recovery manifests.
- **Quality-aware satellites:** never mix mismatched radar orbit geometry or optical cloud-skipped images with valid crop measurements.
- **No unsupported diagnosis:** NDVI/NDMI/SAR/ET0 are signals or modeled context, not direct disease/yield/soil-water diagnoses.
- **Scoped ownership:** authenticate at routes and validate access before retrieving private fields, media or crop cycles.
- **Idempotent processing:** ingestion retries must preserve completed observations and historical NDVI-only records.
- **Contract stability:** preserve public route paths, Pydantic responses, migration heads and canonical GCS paths unless separately planned.
- **Graceful failures:** weather provider errors may remove context, but cannot overwrite canonical field records; GCS recovery manifest refresh must not invalidate committed data.

## Documentation convention

Every Python module begins with an informative module docstring naming its responsibility. Use comments for *why* constraints exist, especially time windows, fallback provenance, orbit comparability and transaction boundaries. Avoid line-by-line comments that restate what each assignment does. Put business logic under services or repositories; keep FastAPI route functions short where practical.

## Verification

Run from repository root:

    python tools/check_backend_docs.py

API checks:

    cd services/api
    uv sync --frozen
    uv run alembic current --check-heads
    uv run --with pytest python -m pytest -q tests
    uv run python -m compileall -q app scripts

Worker checks:

    cd services/satellite-worker
    uv sync --frozen
    uv run --with pytest pytest -q tests

Tiler checks:

    cd services/tiler
    uv sync --frozen
    uv run --with pytest pytest -q tests

GitHub Actions checks fresh PostGIS migrations, API imports/tests, worker, tiler and unchanged frontend build/lint. No database migration is needed for this refactor.

**Future work:** Very large existing spatial-change and media-processing modules should be split further only around tested cohesive responsibilities, not mechanically by line count.
