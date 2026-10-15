# Satellite Worker

Processes optical, radar, and thermal satellite data for Farm Platform fields.

Sources and derived metrics:

- Sentinel-2 L2A: NDVI, NDRE, NDMI, GNDVI, EVI2, NDWI, SAVI, MSAVI, BSI,
  NDTI, CCCI, RECI, MCARI.
- Sentinel-1 RTC: VV dB, VH dB, VV/VH ratio, dual-pol RVI. Radar is
  cloud-independent and is stored as a separate observation source.
- Landsat Collection 2 Level-2: land-surface temperature (LST) in °C with
  QA_PIXEL cloud/shadow/snow masking.

The worker writes temporary COGs, publishes canonical objects to private GCS,
stores metric rows in PostgreSQL, and calculates metric-aware relative anomaly
zones where a scientifically appropriate anomaly rule exists.

## Source layout

- `sources/sentinel2/`: optical bands, reflectance, cloud masks, indices
  and optical processing pipeline.
- `sources/sentinel1/`: RTC radar processing and relative-orbit metadata.
- `sources/landsat/`: Landsat Level-2 thermal processing.
- `sources/stac.py`: remote satellite imagery discovery.
- `processing/`: cross-sensor raster tools and anomaly algorithms.
- `ingestion/`: worker event loop and processor scheduling.
- `persistence/`: database connection, scenes/metrics and ingestion jobs.
- `storage/`: GCS access, canonical keys, COGs and manifests.
- `cli/`: explicitly invoked backfill, maintenance and batch commands.

The older top-level Python files remain small import/command compatibility
shims. They do **not** duplicate processing logic. New code should import
canonical package modules. Existing `satellite-ingestion-worker` and
`python -m satellite_worker.process_*` commands remain valid.

See [backend architecture](../../docs/BACKEND_ARCHITECTURE.md).

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

The worker also creates idempotent incremental jobs for every field. Each job
runs Sentinel-2 optical, Sentinel-1 RTC radar, and Landsat thermal processors.
Incremental jobs search a recent lookback window but skip scenes already
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

Cloud-covered optical scenes are recorded with a terminal processing status,
date, scene identifier, and available cloud/field-coverage metadata. They are
not retried and they do not receive fake metric rows. Sentinel-1 radar scenes
are independent acquisitions, so a cloudy optical date can coexist with a
nearby radar date containing only the four SAR metrics.

## Process one field manually

```bash
uv run python -m satellite_worker.process_field \
  --field-id <FIELD_UUID> \
  --start 2026-10-01 \
  --end 2026-10-14
```

Manual processing remains available when an explicit reprocess is needed:

```bash
uv run python -m satellite_worker.process_sentinel1_field \
  --field-id <FIELD_UUID> --start 2026-10-01 --end 2026-10-14

uv run python -m satellite_worker.process_landsat_field \
  --field-id <FIELD_UUID> --start 2026-10-01 --end 2026-10-14
```

Automatic jobs invoke all three processors with `--skip-existing`.

A command exits non-zero if any selected scene fails. Raster publishing stages
and verifies new COGs before promotion and restores previous canonical objects
if a rerun fails during promotion.

## Tests

```bash
uv run --with pytest pytest -q tests
```
