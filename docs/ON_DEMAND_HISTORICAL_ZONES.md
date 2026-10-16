# Historical Zones — only final seasonal averages are stored

This replaces the previous approach of requiring multi-year `satellite_observations`
and historical per-scene GeoTIFFs. **Nothing starts automatically.**

## How it works

1. Open a saved field → **Historical Zones**.
2. Select a crop cycle (e.g. Rice), with valid planting and harvest/expected
   harvest dates. Select up to six historical years (e.g. 2020–2025).
3. Press **Calculate missing seasons**. An authenticated FastAPI request inserts
   only rows that do not already have a valid result. Clicking twice will
   not duplicate work; failed jobs can be retried deliberately.
4. The separate manual background worker processes each selected year. It
   streams cloud-screened field windows from Earth Search Sentinel-2 L2A COGs
   to local memory; it never inserts the original scenes into
   `satellite_observations`, never writes historical imagery to GCS, and
   does not retain temporary GeoTIFFs.
5. For each year, only a compact field-shaped **seasonal NDVI mean grid**
   (bounded to 64 by 64, typically much smaller), coverage and provenance
   metadata, and status/error remain in Postgres.
6. Select any previously calculated years and click **Show average**. The API
   combines saved annual composites, assigning each year equal weight and
   requiring >=2 years per cell when combining multiple seasons. This is
   immediate and **does not download raw satellite imagery**.
7. Combined average map is shown first; every saved rice-season average map
   appears beneath it by year, with exact or estimated calendar provenance.

The saved result is a small raster-like numeric grid; colored low/near/high
areas are derived from each map's field mean at render time. The current
relative thresholds are illustrative (NDVI +/-0.08); they are **not calibrated
crop productivity, soil quality, yield, fertilizer recommendations or field
diagnoses**. These are *vegetation index zones*, not actual economic
productivity zones. A 10m analysis pixel is not a plot-level diagnosis.

## One-time migration

```bash
cd services/api
uv run alembic upgrade head
```

A single table `seasonal_zone_composites` is added. Existing scenes,
metrics, farms, crops, anomaly tables, WhatsApp state and cloud storage are
not changed. There is no historical mass import or automatic backfill.

## Run the background processor

In its own terminal alongside your existing services:

```bash
cd services/satellite-worker
uv sync --frozen
uv run python -m satellite_worker.ingestion.seasonal_zones --loop
```

`--loop` waits for **manually created** jobs; it does not schedule them.
For one queued season only, use `--once`. It uses your existing
`services/satellite-worker/.env` database/STAC settings.

An active internet connection is required *during a calculation*, not to
reopen the saved historical reports. Large backfills can take time and
send range requests to the STAC/COG provider; the UI polls DB job status.
The worker does not run from FastAPI's request handler. Keep it running
until status changes to Completed or Failed.

## Validity and sample selection

- Only completed previous calendar years, maximum six, chosen manually.
- The selected current crop cycle determines the reference crop and season.
  Saved actual historical crop-cycle planting and harvest dates are used
  when present; otherwise the selected cycle calendar is projected to a
  prior year and the result is explicitly flagged as *estimated dates*.
- Search is one growing season at a time. At most one comparatively clear
  acquisition per 10-day window; up to 18 dates distributed across that
  season. Require >=3 usable dates with >=80% field-valid pixels.
- Existing Sentinel-2 reflectance, cloud-mask and NDVI processing helpers
  are reused. Per-scene data are aligned to one field-specific geographic
  grid, accumulated, discarded, and never persisted.
- A composite cell requires >=2 contributing scenes and sufficient field
  coverage. Multi-year combination requires >=2 annual means per cell when
  comparing 2–6 years.
- If field geometry changes, old results are flagged stale, never silently
  mixed with the new boundary. Failed years show an explicit retry action.
- No private GCS or tiler service is exposed to ngrok. All requests use
  the existing authenticated `/api/v1` Vite proxy.

## API

- `GET /fields/{field}/seasonal-zones?crop_cycle_id=<uuid>` — years and status
- `POST /fields/{field}/seasonal-zones/calculate` — explicit enqueue
- `POST /fields/{field}/seasonal-zones/combine` — combine completed summaries

Every endpoint checks Firebase-backed ownership of both the field and crop
cycle, as well as their relationship.

## Limitations

Real historical productivity is not interchangeable with season-mean NDVI.
Comparing unequal crop stages, weather, rice varieties, planting practices,
and different number of clear scenes can bias the result. Satellite
resolution and cloud availability can leave fields without enough valid
observations. A saved year is available only after its calculation succeeds;
years without suitable imagery must not be filled with invented values.

The separate old `/spatial-history` API remains for existing recent
ingested anomaly records, but its old automatic historical-zone UI was
removed. This new Historical Zones tab is the manual multi-year workflow.

The worker is a dedicated process; automatic job recovery after an
unexpected machine restart is intentionally not enabled until safe worker
lease/cancellation semantics are added. Restarted workers do not silently
repeat costly unfinished years; investigate/requeue explicitly.
