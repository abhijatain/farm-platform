# Reset-to-one-field demo: deliberately NOT an automatic production wipe

## What this branch prepares

The farmer-supplied GeoJSON has exactly **one MultiPolygon member**, which
is valid as a single PostGIS Polygon. That **private geometry is not committed
into this public repository**. Provide the GeoJSON file on the machine running
the seed command.

- One verified Firebase test account (must already exist in the selected
  Firebase project, and its phone number must match the CLI arguments).
- One farm and **one** field with the supplied geometry.
- Four separate farm seasons / crop cycles: Wheat 2025 (Rabi 2024–25),
  Rice 2025 (Kharif), Wheat 2026 (Rabi 2025–26), Rice 2026 (Kharif).
- A comprehensive fictional activity diary for each cycle covering soil
  sampling, tractor cultivation, seed/nursery preparation, sowing/transplanting,
  fertility and water management, field scouting, weed/disease/pest treatment
  examples, crop-stage inspections, harvest, threshing, drying, grading,
  storage, transportation and sale.
- Fictional harvest amounts computed from field size, **explicitly marked
  synthetic**. No specific spray product/dose, sensor measurement, disease
  diagnosis, actual grower action or real yield is claimed.
- Four persisted multi-source ingestion jobs spanning the historical crop
  windows. The existing worker must fetch **real Sentinel-2, Sentinel-1 and
  Landsat** scenes, compute index metrics and place clipped COGs in GCS.
  **The seed does not insert simulated NDVI/radar/thermal values.**

## DESTRUCTIVE RESET REQUIRES SEPARATE CONFIRMATION

The user requested deletion of all GCS objects, PostgreSQL application data,
and Firebase Authentication users. **This repository branch does not do any
of those destructive actions,** does not include deletion credentials and
cannot access the live infrastructure. Never interpret `--apply` as a wipe.

Before considering an irreversible wipe:

1. Confirm the exact target **Firebase project ID**, **GCS bucket name**, and
   **PostgreSQL host and database name**. All may also serve unrelated apps.
   Identify staging/test vs production, and inventory counts and object
   prefixes. If the GCS bucket has other projects' objects, do NOT clear the
   whole bucket.
2. Stop API and background workers so they cannot repopulate stale records.
3. Export Firebase users, take an encrypted PostgreSQL backup and snapshot
   GCS objects. Verify recoverability/retention and billing consequences.
4. Obtain **separate explicit approval of the enumerated targets** before
   deleting. Prefer fresh isolated test resources instead of deleting
   production. Do not alter/decommission the Firebase Auth phone-login
   configuration or delete the Firebase project itself.
5. Keep **Alembic schema and migrations**. Data reset is not the same as
   dropping PostgreSQL/PostGIS tables. When reset is done, migrate to head.
6. Create/retain a single test Firebase phone user; obtain its UID, then
   seed the empty DB. Using arbitrary made-up Firebase credentials is invalid.

## Seed commands (from services/api)

Preview with your local boundary file (no DB or cloud I/O):

```bash
cd services/api
uv run python -m app.cli.seed_four_crop_demo \
  --geojson "/path/to/Field_14253841_boundaries_10_16_2026.geojson"
```

After an **independently reviewed reset** of a dedicated nonproduction DB,
create/verify a real Firebase phone test account, retrieve its Firebase UID,
then run:

```bash
uv run alembic upgrade head
uv run python -m app.cli.seed_four_crop_demo \
  --geojson "/path/to/Field_14253841_boundaries_10_16_2026.geojson" \
  --firebase-uid "UID_FROM_FIREBASE_AUTH" \
  --phone "+91YOUR_TEST_PHONE" \
  --confirm-db-name "EXACT_DATABASE_NAME" \
  --apply
```

The seed intentionally **refuses** production environments, mismatched
database names, unverified Firebase identities and all **nonempty** DBs.
It never deletes another account or existing field. Use the same nonproduction
PostgreSQL database from the API and satellite worker.

## Satellite processing and QA

The seed queues four historical jobs but does **not** execute them. From
`services/satellite-worker`, after configuring matching DB, GCS credentials
and STAC endpoint access, run the existing worker:

```bash
uv run python -m satellite_worker.ingestion.worker --once
```

This might take substantial time, network usage, storage and billing.
Automatic incremental ingestion can create additional jobs for the same field,
but the dedupe pipeline keeps canonical scene records. Monitor logs and retry
failed jobs rather than fabricating data.

From `services/api`, find the field ID using the authenticated UI/API or DB:

```sql
SELECT id, name FROM fields;
SELECT crop_name, started_on, planted_on, harvested_on, status
FROM crop_cycles ORDER BY started_on;
SELECT job_type, start_date, end_date, status, last_error
FROM satellite_ingestion_jobs ORDER BY start_date;
```

Then verify real satellite coverage for all four crop cycles:

```bash
uv run python -m app.cli.verify_four_crop_satellite \
  --field-id "FIELD_UUID"
```

A nonzero exit means a crop is missing one or more core optical/radar/thermal
metrics or lacks enough usable NDVI dates. **Do not claim all four crops have
full satellite coverage until this check succeeds.** Cloud/no-data months may
limit available imagery; the application should show that honestly.

Historical Zone averages are separate, manually requested calculations using
`satellite_worker.ingestion.seasonal_zones --once` only AFTER a user clicks
Calculate in the Historical Zones tab. The demo seed does not silently trigger
those on-demand calculations.
