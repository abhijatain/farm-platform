# Farm Platform API

FastAPI service for authentication, farms, fields, seasons, crop cycles,
activities, satellite metadata, anomaly queries, and farmer media.

## Setup

```bash
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

The database must be PostgreSQL. The initial migration enables PostGIS before
creating geometry columns, so a new empty database can be migrated from zero.

## Tests

```bash
uv run --with pytest pytest -q tests
```

## Maintenance

```bash
uv run python scripts/dump_db_schema.py
uv run python scripts/cleanup_stale_media_uploads.py --dry-run
```

Historical satellite observations may legitimately contain only NDVI. Database
audits report metric coverage informationally and do not backfill those rows.
