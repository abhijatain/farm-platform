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

## Authorized clean reset of the existing disposable demo resources

The user confirmed that their present Farm Platform data was made up and
requested a permanent reset. The guard remains necessary because Firebase,
GCS and PostgreSQL **may not share exclusive ownership with this application**,
and a deletion cannot be undone.

**Prerequisites:** Stop FastAPI, satellite ingestion worker, historical zones
worker, any media processor and scheduled incremental jobs. Confirm this is an
exclusive *nonproduction* deployment. Select the correct local `services/api/.env`
(or provide the same environment variables to the command). Back up anything
you actually wish to keep. **Do not share .env, Firebase credentials or passwords.**

First perform the live **read-only inventory**:

```bash
cd services/api
uv run python -m app.cli.reset_test_data
```

It prints the database host/name, Firebase project ID, GCS bucket,
and counts of application rows, Firebase users and all accessible
Cloud Storage object generations. No deletions occur.

Review that ALL the displayed resources belong only to this Farm Platform
demo. The following command only succeeds if you type each exact target from
the inventory (replace placeholders with actual names; do not send secrets):

```bash
uv run python -m app.cli.reset_test_data --apply \
  --confirm-db-host "EXACT_HOST" \
  --confirm-db-name "EXACT_DATABASE_NAME" \
  --confirm-firebase-project "EXACT_FIREBASE_PROJECT_ID" \
  --confirm-gcs-bucket "EXACT_GCS_BUCKET_NAME" \
  --acknowledge "PERMANENTLY ERASE ALL DEMO USERS DATA AND OBJECTS"
```

It deletes every accessible object generation in that one named GCS bucket,
all Auth users in that one named Firebase project, and rows from every
registered Farm Platform public-schema table in that one PostgreSQL
database. **It leaves `alembic_version`, PostGIS `spatial_ref_sys`, all
schema definitions and the Firebase project/bucket configuration intact.**

The command requires `ENVIRONMENT` be a test/development/staging value,
an exact match on all resource IDs, and a schema match; it will refuse
unexpected database tables. PostgreSQL TRUNCATE uses one transaction
and intentionally omits CASCADE to avoid silently wiping external tables.
No cross-service transaction is possible, so if a cloud delete fails
partway through, resolve the error and rerun the inventory.

**GCS retention and soft-delete** may retain recoverable versions after a
delete or disallow deletion. A successful command verifies that normal
listings are empty but does *not* bypass bucket retention policy. Check
GCS settings if immediate irreversible erasure is required.

Now your Firebase Auth user list is also empty. **Sign back in through
real Firebase phone verification**, which creates a new Auth user/UID;
do not manually invent a verified identity. Use that UID + E.164 number
with the separate seed command below.

## Alternative: manually erase Firebase and Cloud Storage

If Cloud Storage inventory fails with HTTP **403** because the Firebase
Admin service account cannot read `storage.buckets.get`, you do **not** need
to grant that service account broader cloud roles merely to reset demo data.

In your own Google Cloud Console, first check that `jatain-farm` belongs
exclusively to the disposable Farm Platform demo. Navigate to **Cloud Storage
→ Buckets → jatain-farm → Objects**, select and delete only the demo objects.
Review bucket versioning and soft-delete/retention rules and check noncurrent
generations before considering the deletion complete. Keep the bucket itself,
its IAM policy and application configuration. If the bucket contains any
non-demo objects, delete only the owned object prefixes instead of everything.

In Firebase Console, open **Authentication → Users** for the confirmed
project `farm-ef16c`. Delete only the disposable demo users. If you want to
keep the already verified test login for seeding, **leave that user in
Firebase Auth** and obtain its UID. If all are deleted, sign in via the normal
Firebase phone-auth flow once more to recreate the test account before
running the seed. Do not delete the Firebase project or disable Phone login.

For PostgreSQL you can now run a **separate database-only inventory** with
*no Firebase or GCS calls whatsoever*:

```bash
cd services/api
uv run python -m app.cli.reset_test_data --database-only
```

The returned database host and name must match the intended disposable
database. Stop FastAPI and all workers before erasing, and take a backup if
there's anything you wish to recover. For the currently confirmed local
development database, run:

```bash
uv run python -m app.cli.reset_test_data \
  --database-only --apply \
  --confirm-db-host "localhost" \
  --confirm-db-name "farmdb" \
  --acknowledge "PERMANENTLY ERASE FARM PLATFORM DATABASE DATA"
```

The command verifies the exact database name and host plus the nonproduction
environment, accepts only known Farm Platform application tables and the
structurally verified abandoned `whatsapp_outbox` table, and truncates those
tables without `CASCADE`. It **does not contact or delete** Firebase users
or Cloud Storage objects, and verifies that application rows are zero.
The database schema, PostGIS system tables and `alembic_version` are
preserved.

**Important migration caveat:** An old WhatsApp-only branch may have left
an `alembic_version` revision that does not exist in `main`.
After the data reset, inspect `SELECT version_num FROM alembic_version;`
and reconcile the migration graph *before* blindly running
`alembic upgrade head` or `alembic stamp`. Truncating rows alone does
not repair an orphaned migration revision.

**Subsequent ingestion caveat:** Manually deleting old GCS objects does not
give the satellite ingestion worker permission to upload fresh rasters.
Ensure the worker's *separate* GCS identity has correctly scoped object
write/read privileges before starting historical backfill. Avoid
granting broad bucket-admin permissions to Firebase Auth identities.

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
