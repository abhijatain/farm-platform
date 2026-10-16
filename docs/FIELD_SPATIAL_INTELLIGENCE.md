# Field Intelligence — combined zones, anomalies, satellite and phenology

This branch delivers the **first integrated field-intelligence workflow** for
four roadmap areas (historical zones, anomaly tracking, multi-sensor comparisons,
crop phenology), reusing existing PostgreSQL/PostGIS, GCS, satellite worker, and
the responsive field UI. It does not add tables or data migrations.

## New authenticated APIs

- `GET /api/v1/fields/{id}/spatial-history?metric_type=ndvi&years=10`
  - Owner-checked historical, quality-gated Sentinel-2 observations.
  - Uses existing field-relative anomaly polygons, sampled on resolution-aware,
    clipped geospatial cells; optional last-two-date transition coverage.
  - Returns repeated-relative-low/high *candidate scouting/management zones*
    and new/persistent/recurring/resolved relative anomaly areas using the latest three qualifying dates.
  - Requires 80% valid pixel coverage; refuses <8 valid pixels and unsupported
    metric types. Stable multi-year labels require >=6 usable acquisitions from
    >=2 calendar years; otherwise the API emits `short_history` and
    **no historical zones**.
  - All areas are approximated from the polygon shares scaled to a PostGIS
    geodesic field area, and all outputs are **relative field comparisons**.
    They are NOT measured yield, crop disease, soil fertility or fertilizer
    prescriptions. 3857 cell grids can distort shapes at high latitudes.
  - Requests are bounded: <=10 years, at most one best-quality scene/month plus the four most recent qualifying scenes, and <=1200 stored
    anomaly polygons. If either data cap is reached the candidate zone output
    is suppressed to avoid presenting a partial history as complete.

- `GET /api/v1/fields/{id}/observation-intelligence?years=2`
  - Latest and immediately preceding **distinct valid dates** for NDVI, NDMI,
    NDRE and same-orbit Sentinel-1 VV/VH/RVI.
  - Both dates require >=80% valid coverage. Unidentified radar orbits are
    excluded. This descriptive difference needs **two passes**, not a
    confirmed growth stage. Conservative crop-stage screening remains separate
    and unchanged. No "healthy/stressed" interpretation.

- `GET /api/v1/crop-cycles/{id}/phenology-intelligence`
  - Owner-scoped, farmer-confirmed vs provisional crop stage; stage-dependent
    optical index context; planting-age-aligned NDVI comparisons to earlier
    crop cycles of the same crop, within +/-10 days.
  - Cross-year planting-age comparisons are not certified growth-stage matches
    or causal explanations. Missing planting dates and cloud-skipped scenes
    produce empty comparison lists, never fabricated values.
  - Wheat/rice/maize show approximate BBCH *reference families* only.
    Mango, litchi, guava, chikoo/sapota have **manual-only perennial stages**.
    Cultivar, photoperiod and regional calibration remain unvalidated; users
    must record real crop stage observations.

The monthly sample preserves older calendar years rather than limiting the\nanalysis to the latest densely sampled season. Four recent passes are retained\nto show new/persistent/resolved transitions; this is not an unbiased\nper-date frequency estimate when observations are missing.\n\n## UI and testing

The field Satellite tab provides a selectable NDVI/NDMI/NDRE historical zone
and recent anomaly transition map, acreage, data completeness warnings,
a table of two-pass radar/optical differences by source/orbit, and growth-stage
context/history on desktop and mobile. Spatial history is shown even when
field imagery has not yet been ingested (with explicit missing-data states).

Run:

```bash
cd services/api
uv run --with pytest python -m pytest -q tests/test_field_intelligence.py
cd ../../apps/web
pnpm build && pnpm lint
```

For end-to-end testing, start API, local Vite with `VITE_API_URL=/api/v1`,
and `ngrok http 5173`; mobile calls are same-origin HTTPS and continue using
the Firebase ID token.

## Known limits / future validation before agronomic use

- Full 5–10-year zone detection requires **actually ingested** historical
  scenes: 10-year query windows do not create observations. Existing default
  initial ingestion only backfills 90 days. Use bounded/manual historical
  Sentinel-2 ingestion and check data licensing/costs before expanding.
- The candidate management-zone surface is **repeated field-relative anomaly
  frequency**, not a direct multi-year raster productivity model. A true
  stable low/medium/high vegetation-performance product needs stage-matched
  historical pixel stacks and ground-truthed management/yield data.
- No named persistent-zone IDs across every scene: the v1 transition map
  operates on sampled cells and the two latest qualifying acquisitions;
  per-zone longitudinal IDs, counts and audit trails require a later model.
- Cultivar/regional crop calendars, BBCH calibration, orchard phenology
  and stage-matched historical raster maps require field pilots and more
  observations. Unvalidated physiological predictions stay disabled.
- Minimum crop/field pixel requirements, cloud/date matching and optical-SAR
  mixing are enforced conservatively. Scouting verification comes in the
  separate planned scouting workflow, not an automatic diagnosis here.
