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

## Automatic ingestion

Run one long-lived ingestion worker:

```bash
uv run satellite-ingestion-worker
```

The worker polls PostgreSQL for queued jobs. New fields queue a 90-day
historical backfill in the same transaction as field creation. Fields that
existed before automatic ingestion was deployed and still have zero satellite
observations are bootstrapped automatically when the worker starts.

The worker also creates idempotent incremental jobs for every field. Each
incremental job searches a recent lookback window, but skips scenes already
complete in PostgreSQL. Historical pre-v2 observations that already have
metrics—including NDVI-only observations—are deliberately preserved and are
never filled in by automatic ingestion.

For scheduled environments such as cron or Cloud Run Jobs, drain the queue and
exit instead:

```bash
uv run satellite-ingestion-worker --once
```

A failed job is retried after the configured delay until its attempt limit is
reached. Stale running jobs are recovered when the worker starts.

## Process one field manually

```bash
uv run python -m satellite_worker.process_field \
  --field-id <FIELD_UUID> \
  --start 2026-10-01 \
  --end 2026-10-14
```

Manual processing remains available when an explicit reprocess is needed.
Automatic jobs invoke the same processor with `--skip-existing`.

A command exits non-zero if any selected scene fails. Raster publishing stages
and verifies new COGs before promotion and restores previous canonical objects
if a rerun fails during promotion.

## Tests

```bash
uv run --with pytest pytest -q tests
```
