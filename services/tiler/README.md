# Farm Tiler (internal service)

TiTiler-based raster service for owner-authorized private Google Cloud Storage
COGs. **The browser never connects to this service.** FastAPI authenticates
the farmer and checks ownership before proxying a raster tile, preview or
change summary to the internal tiler.

## Source organization

`main.py` registers FastAPI/TiTiler endpoints. Pixel-wise change calculations
live in `services/change.py`; `storage/gcs_path.py` validates private GCS
dataset locations. See [backend architecture](../../docs/BACKEND_ARCHITECTURE.md).

## Local setup

```bash
cd services/tiler
cp .env.example .env
uv sync
# Add GCS_BUCKET_NAME, credentials and SATELLITE_TILER_SHARED_TOKEN to .env.
# Use the SAME random SATELLITE_TILER_SHARED_TOKEN in services/api/.env.
uv run uvicorn farm_tiler.main:app --app-dir src --host 127.0.0.1 --port 8081 --reload
```

Create the token locally with `python -c 'import secrets;
print(secrets.token_urlsafe(48))'` (as a one-line shell command). Never add
it to Git or any `VITE_` browser variable. Without a matching token, API
raster requests fail closed.

The service **must not** be reachable from the public internet or exposed
by ngrok, Vite, a reverse proxy, a public load balancer or an open firewall.
Do not use `--host 0.0.0.0` for this service. In future containerized
deployments, put API and tiler on a trusted private network and review the
loopback-only outbound URL guard before changing it.

The web app uses the authenticated FastAPI tile endpoint via MapLibre's
`farmtile:` protocol, **not** `VITE_TILER_URL`.

See [secure satellite tiler setup and smoke tests](../../docs/SECURE_SATELLITE_TILER.md)
before merging or deploying.
