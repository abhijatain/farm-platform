# Satellite Worker

Processes Sentinel-2 L2A scenes for Farm Platform fields.

The worker computes the configured satellite metrics, writes temporary COGs,
publishes canonical objects to private GCS, stores metric rows in PostgreSQL,
and calculates metric-aware relative anomaly zones.

## Setup

```bash
cp .env.example .env
uv sync
```

## Process one field

```bash
uv run python -m satellite_worker.process_field \
  --field-id <FIELD_UUID> \
  --start 2026-10-01 \
  --end 2026-10-14
```

A command exits non-zero if any selected scene fails. Raster publishing stages
and verifies new COGs before promotion and restores previous canonical objects
if a rerun fails during promotion.

## Tests

```bash
uv run --with pytest pytest -q tests
```
