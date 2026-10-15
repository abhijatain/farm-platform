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
