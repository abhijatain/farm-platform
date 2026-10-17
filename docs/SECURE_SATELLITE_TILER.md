# Private satellite raster deployment (required before public access)

Implements the audit's **S1/S2** controls: raster paths must not leave the backend,
and no raw TiTiler endpoint is available without a server-to-server secret.
PR intentionally defaults to *fail closed*, even in local development.

## First local smoke test

Generate a strong secret **on your own computer**, e.g.:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Copy the SAME exact secret into these LOCAL (ignored) env files:

- `services/api/.env`: `SATELLITE_TILER_SHARED_TOKEN=<secret>`
- `services/tiler/.env`: `SATELLITE_TILER_SHARED_TOKEN=<secret>`

Do NOT prefix this variable with `VITE_`. Never upload or paste the secret.

Start the API and tiler (and optionally web):

```bash
cd services/tiler
uv run uvicorn farm_tiler.main:app --app-dir src --host 127.0.0.1 --port 8081
# Separate terminal
cd services/api
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
# Separate terminal
cd apps/web
pnpm dev --host 0.0.0.0
```

The API's `SATELLITE_TILER_INTERNAL_URL` defaults to
`http://127.0.0.1:8081`. Its SSRF guard currently requires loopback; a
containerized deployment needs a safely reviewed private sidecar/network
arrangement before changing that guard. Never expose TiTiler via ngrok,
public load balancer, firewall, Vite dev proxy, reverse-proxy path or CDN.
The Vite frontend no longer uses `VITE_TILER_URL`.

Verify:

```bash
# Direct public tiler access must fail even with a known gs:// path.
curl -i 'http://127.0.0.1:8081/cog/info?url=gs%3A%2F%2Fexample%2Fusers%2Fx%2Fndvi.tif'
# Expected HTTP 401 with a configured secret; HTTP 503 if unset.

# Field owner must be authenticated (Firebase Bearer), not a raw URL key:
curl -i 'http://127.0.0.1:8000/api/v1/fields/FIELD_UUID/satellite-observations/OBS_UUID/tiles/ndvi/12/1024/1536.png'
# Expected HTTP 401/403 for anonymous requests; a real owner with valid
# token can load their own raster, another owner must get 404.
```

In a signed-in browser, MapLibre uses a private `farmtile:` protocol to
fetch raster bytes from FastAPI using a Firebase ID token. Inspect the Network
tab: no `gs://` URIs, no raw TiTiler URLs, and no token in query parameters.
Switch fields, optical metrics, radar/thermal and image dates. Watch tile
latency and memory, and verify ngrok HTTPS still passes API authorization.

## Remaining P0 operations (not automatically solved by these code changes)

- **GCS manifests:** API and worker stop writing user names or phone numbers
  to new user manifests. Existing `users/{id}/user.json` and retained
  generations/soft-deleted copies must be inventoried and rewritten/removed
  in Cloud Storage according to deletion policy. Check for PII in other keys,
  object metadata, old versions and logs. This PR does not touch live GCS.
- **PostgreSQL:** Configure automated encrypted backups and point-in-time
  recovery, put backup objects in a SEPARATE restricted bucket, and practice
  a restore. No backup job has been deployed by this PR.
- **IAM:** Use read-only access for private tiler GCS identity and narrow
  privileges for the ingestion worker's object writes. Neither identity
  should depend on a privileged Firebase Authentication service account.
- **Observability and abuse:** per-user tile quotas, request limits, latency
  monitoring and availability alerts are future production work.
- **Threat test:** verify owner A cannot fetch owner B's tile using IDs or
  guessed observation paths. The middleware secret does NOT replace API
  user authorization.

**Never merge this PR directly into an already running release without
configuring and smoke-testing the two server processes.** With the secret
unset, tile rendering deliberately stops instead of falling back to
unauthenticated access.
