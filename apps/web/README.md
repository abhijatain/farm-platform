# Farm Platform Web

The React/Vite frontend for mapping, farm records and field analysis.

## Test WhatsApp linking locally

First run the FastAPI backend on port 8000 with a development PostGIS
database migrated through PR #16, and configure the Meta webhook secrets and
`WHATSAPP_PHONE_NUMBER_ID` in `services/api/.env`.

Start the web app:

```bash
cd apps/web
pnpm install --frozen-lockfile
pnpm dev
```

For ngrok-based WhatsApp / Firebase testing, use one HTTPS tunnel to Vite:
```bash
# from a second terminal; FastAPI remains running on 127.0.0.1:8000
ngrok http 5173
```
Set `VITE_API_URL=/api/v1` in `apps/web/.env` and restart Vite.
The development server proxies `/api/*` to `http://127.0.0.1:8000`,
including the Meta webhook at `/api/v1/webhooks/whatsapp`. Configure
Meta's callback URL to `https://YOUR-NGROK-DOMAIN/api/v1/webhooks/whatsapp`.
Also authorize that hostname under Firebase Authentication's Authorized
domains. Do not run a second ngrok tunnel on the same reserved domain.
This proxy is for Vite development; production must configure its own
reverse proxy. The app's `VITE_API_URL` must not remain set to a separate
HTTP localhost or LAN backend URL during HTTPS testing.

For a **real mobile number**, set `VITE_FIREBASE_TEST_PHONE_AUTH=false`
in `apps/web/.env`; enable Firebase Phone sign-in, allow your country's SMS
region and an authorized HTTPS web domain in Firebase Console. Your old
fictional/seeded account is a distinct Firebase user with separate farms.
Sign out and verify your own phone through actual SMS before starting linking.
If real SMS login fails on localhost, follow Firebase's supported authorized
HTTPS-domain setup (see `services/api/README_WHATSAPP.md`).

Sign in with **Firebase phone authentication**, then click the **chat-bubble
WhatsApp icon** near the bottom of the left navigation rail. In the dialog:

1. Choose Punjabi, Hindi or English.
2. Explicitly accept WhatsApp *service-message* consent.
3. Click **Generate linking code**. Only the signed-in Firebase account may
   request a code.
4. Click **Open WhatsApp** to prefill the LINK message, when the business
   receiving number is configured, or click **Copy** and send the exact
   `LINK <code>` message within ten minutes
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

**Read-only WhatsApp menus:** PR #16 adds WhatsApp interactive lists with
"My farms", "My seasons" and "My fields", after a real signed inbound LINK
event. It queues replies and sends them only through an explicitly enabled
Meta Graph API outbox worker. See `services/api/README_WHATSAPP.md`.
Since the WABA is reportedly active again, use the read-only Meta token/phone
check and then one authorized live recipient to validate the flow. An active
account alone does not prove the specific sender number is registered.

Avoid uploading secrets, access tokens, or one-time linking codes in screenshots.

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
