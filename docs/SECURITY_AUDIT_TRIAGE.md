# Farm Platform third-party audit triage (17 October 2026)

This is a scoped implementation record, not a claim that the entire pasted
305-file audit has been re-verified or completed. The independent review
explicitly lacked a working PostGIS/GCS environment. Verify each finding
against running services and deployments before closing it.

## Phase A: Immediate security access controls — draft PR #22

- **S1: Unauthenticated TiTiler** — addressed in code with internal token
  and per-user API tile proxy. Must still verify runtime network binding,
  Firebase cross-user isolation and both servers' secrets before merge.
- **S2: Internal gs:// URIs in API responses** — serialization schema
  excludes raster_uri and exposes has_raster. Browser now loads tiles by
  field/observation/metric IDs; sanitize nested metadata path strings.
- **S8: PII in GCS user manifests** — stop writing name and phone to newly
  produced user manifests in both API and worker. **Existing buckets/object
  versions are not cleaned by PR #22.** Add a reviewed user export/deletion
  workflow with correct retention policy.

## Phase B: Before a public deployment (not implemented here)

- **O6:** Separate restricted backup bucket, scheduled Postgres backups and
  tested restore/PITR. The current database reset scripts are *not* backups.
- **S6:** Explicit production environment validation, strict CORS, security
  headers/CSP, and remove developmental auth fallbacks.
- **S5:** Constrain ffmpeg/ffprobe processing and image dimensions; shift
  untrusted media processing to a separately supervised queue.
- **S3:** Backed rate limiting on upload, raster and expensive spatial APIs;
  429/Retry-After with tests.
- **O1/O2:** Production deployment artifacts, structured logging, durable
  worker supervision, failed-job visibility, full health checks and alerts.
- **Q2/Q5/S7:** Frontend unit/E2E tests, auth cross-user tests, security
  dependency scanning, branch protection and required GitHub checks.
- **R1:** Decide and publish an appropriate software license (owner decision).
- Explicitly audit Firebase/GCS/secret IAM and legally compliant account
  deletion, including backups and object soft-delete generations.

## Phase C: Data model and insight product milestones

- **D1/D2:** Multiple harvest records and structured activity inputs/expense
  data — schema and API migration work.
- **I1–I4/I6:** Group correlated vegetation metrics, cross-signal evidence,
  recurring-persistence zones, and season time-series features. Validate
  thresholds and avoid disease/crop-health diagnoses.
- **I10:** Small-field pixel-count warning and growth-stage-aware optical
  interpretation.
- Weather reproducibility/cache, historical comparisons, and media/tiler
  storage reduction follow when measurement/performance evidence exists.
- The backlog's T-series features should be scheduled separately instead
  of silently treating every audit suggestion as a verified bug.

## Completion policy

For any item, attach a concrete test or operational runbook and confirm
real-data behavior (including cross-user security), not just a successful
TypeScript/Python build. The worker already has genuine historical imagery;
use the one-field four-crop demo for the end-to-end UI walkthrough.

Do not merge PR #22 or expose private tiles until the shared secret is
configured in API and tiler and both processes have been restarted.
