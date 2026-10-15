# Farm Platform API

FastAPI service for authentication, farms, fields, seasons, crop cycles,
activities, satellite metadata, anomaly queries, and farmer media.

## Domain-driven service layout

HTTP endpoints stay in `app/api/routes/`. Domain implementations now live
in `app/domains/{activities,crops,media,satellite}/`, with persistent data
models in `app/models/` and response contracts in `app/schemas/`. Domain implementations are imported directly from `app/domains/`. The
`app/services/` directory contains only the current cross-domain weather,
crop-growth and ownership services. No old domain forwarding files remain.

For the full backend dependency rules, see
[`docs/BACKEND_ARCHITECTURE.md`](../../docs/BACKEND_ARCHITECTURE.md).

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
