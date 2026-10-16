# Farm Platform web: mobile reports and HTTPS development

## Run the web app and FastAPI behind one ngrok URL

This is a development-only setup. Start FastAPI from `services/api`:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Start the web app from `apps/web`:

```bash
pnpm install
pnpm dev --host 0.0.0.0
```

Set the following values in `apps/web/.env`, then **restart Vite**:

```env
VITE_API_URL=/api/v1
VITE_FIREBASE_TEST_PHONE_AUTH=false
```

Keep your existing `VITE_FIREBASE_*` project configuration and `VITE_MAPTILER_KEY`.
Use real Firebase phone authentication only on a Firebase-authorized HTTPS domain.
For local-only satellite tiles, start the tiler on `127.0.0.1:8081` and use `VITE_TILER_URL=http://localhost:8081`. The unprotected tiler must **not** be exposed over a public ngrok tunnel when it has access to private farm imagery.

In a separate terminal run:

```bash
ngrok http 5173
```

Open `https://stoneware-refining-flatfoot.ngrok-free.dev` on a phone or
desktop. This branch's Vite `server.allowedHosts` explicitly permits that
hostname; if your ngrok domain changes, update the allow-list to the new exact
host (do not use `allowedHosts: true`). Add that domain in
Firebase Authentication → Settings → Authorized domains as well.

Routing from the **one public HTTPS origin**:
- `/` → Vite UI on port 5173
- `/api/v1/*` and `/health` → local FastAPI on port 8000
- `/tiler/*` → disabled by default. The unsafe development-only opt-in `ENABLE_DEV_TILER_PROXY=true` forwards to port 8081; use only disposable test data and set `VITE_TILER_URL=/tiler` when opting in. Production needs a per-user authorized tile gateway.

`curl -i https://stoneware-refining-flatfoot.ngrok-free.dev/health`
should show a JSON 200 response from FastAPI. The bare
`/api/v1/auth/me` endpoint without a Firebase token should reject as
unauthorized: an authentication error indicates the route is reaching the API.
After signing in, browser Network requests must use the HTTPS ngrok origin
and `/api/v1/...` rather than `http://localhost:8000`; if they do not,
check the actual `.env` value, restart Vite and hard-refresh.

Do not expose Postgres, Firebase Admin credentials, Meta secrets, or the API
directly through ngrok. The public tiler proxy is disabled by default due to private raster access. A mobile phone can access the Vite URL over HTTPS.

## Phone layout and field reports

On narrow screens, use the bottom **Fields / Map** navigation. Selecting a field
opens the map and its field details. Use the swipeable **Satellite / Activities /
Yield / Report** tabs. The Report tab summarizes owner-authorized records for
the selected field and season: actual crop/harvest entries, activity history,
usable satellite NDVI/NDMI, comparative NDVI change and modeled rainfall.
It never guesses absent observations or labels satellite anomalies as diseases.
Use **Print / Save PDF** to create a browser PDF. Desktop layout remains
three-column.

Smoke test on a real phone at around 360–430px wide, plus an iPad/tablet and
desktop: login, farm/season switching, selecting a field, drawing polygon,
scrolling satellite tabs, editing an activity, report loading and printing.
Also test portrait/landscape orientation. Satellite tile rendering over HTTPS is not asserted until an authenticated tile gateway is added. The API proxy is testable locally;
end-to-end verification requires your running backend, Firebase credentials
and ngrok session.

---

# Farm Platform Web

The React/Vite frontend for mapping, farm records and field analysis.

## Test WhatsApp linking locally

First run the FastAPI backend on port 8000 with a development PostGIS
database migrated through PR #15, and configure the Meta webhook secrets and
`WHATSAPP_PHONE_NUMBER_ID` in `services/api/.env`.

Start the web app:

```bash
cd apps/web
pnpm install --frozen-lockfile
pnpm dev
```

Sign in with **Firebase phone authentication**, then click the **chat-bubble
WhatsApp icon** near the bottom of the left navigation rail. In the dialog:

1. Choose Punjabi, Hindi or English.
2. Explicitly accept WhatsApp *service-message* consent.
3. Click **Generate linking code**. Only the signed-in Firebase account may
   request a code.
4. Click **Copy** and send the exact `LINK <code>` message within ten minutes
   from the phone number used at Firebase sign-in to your Meta business number.
5. Use **Check now** (or wait for automatic status refresh) to see `Connected`.
6. Click **Disconnect WhatsApp** to revoke consent and unlink; you can also
   send `STOP` from an already-linked number.

If you close the dialog, the raw code cannot be redisplayed; cancel the
pending link and create a new code. The linking secret is kept in React state
only, never browser localStorage or cookies.

**Meta app still unpublished?** Dashboard-simulated messages do not prove
ownership of your real phone and cannot generally complete live Firebase
account linking. You can still test the web UI, obtain a pending code, refresh,
cancel and unlink. The backend CI integration tests cover full signed linking.

The interface does not yet send WhatsApp replies or expose farm details
through WhatsApp. Avoid uploading secrets, access tokens, or one-time linking
codes in screenshots.

---

# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend enabling type-aware lint rules by installing `oxlint-tsgolint` and editing `.oxlintrc.json`:

```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["react", "typescript", "oxc"],
  "options": {
    "typeAware": true
  },
  "rules": {
    "react/rules-of-hooks": "error",
    "react/only-export-components": ["warn", { "allowConstantExport": true }]
  }
}
```

See the [Oxlint rules documentation](https://oxc.rs/docs/guide/usage/linter/rules) for the full list of rules and categories.
