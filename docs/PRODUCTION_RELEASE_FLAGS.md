# Release controls: launch Farm Platform without WhatsApp

WhatsApp code and historical data remain in the repository/database. Nothing is
deleted or downgraded. The initial production release deliberately keeps the
integration **off by default**, including its HTTP endpoints.

## Environment (two different processes)

In `services/api/.env` (FastAPI, server-side):

```dotenv
WHATSAPP_ENABLED=false
```

In `apps/web/.env` (Vite frontend, build-time):

```dotenv
VITE_ENABLE_WHATSAPP=false
```

These must be set independently. The backend `.env` is read at process startup;
the frontend `VITE_` variable is replaced at **build time**, so restart Vite
locally and rebuild/redeploy the frontend in production. Do not put secrets in
`VITE_` variables. Any change to these flags requires restarting the API and
rebuilding/redeploying the frontend for the values to take effect.

When disabled:

- React doesn't show WhatsApp in either desktop or mobile navigation, and
  it doesn't mount the linking dialog.
- FastAPI doesn't mount any `/api/v1/whatsapp/link` or
  `/api/v1/webhooks/whatsapp` endpoints, even when old Meta secrets still exist
  in the environment.
- `/api/v1/auth/me`, Firebase phone auth, farms, fields, activities, crops,
  reports, satellite/weather APIs and existing records are unaffected.
- No WhatsApp worker should be started. No public Meta webhook subscription
  should point at a disabled endpoint.
- Existing WhatsApp tables, alembic migrations and consent records stay
  untouched.

## Local smoke check before release

From project root, after switching to the release branch:

```bash
cd services/api
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

In a second terminal:

```bash
cd apps/web
pnpm dev --host 0.0.0.0
```

From another terminal:

```bash
curl -i http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/api/v1/webhooks/whatsapp
curl -i http://127.0.0.1:8000/api/v1/whatsapp/link
```

Expected: health 200; WhatsApp requests return **404**. You should not see
WhatsApp controls in the browser, and Sign out must remain visible. Real
Firebase login should still work. The absence of WhatsApp routes in FastAPI
OpenAPI docs is another useful verification.

Do **not** conclude that these flags alone make the whole platform
production-ready. Before public deployment still audit private raster/tile
authorization, HTTPS, allowed origins/hosts, cloud bucket policy, Firebase
authorized domains, media upload auth, database backups, worker process
supervision, weather API licensing and secrets. Ngrok/Vite dev mode is not
a production deployment.
