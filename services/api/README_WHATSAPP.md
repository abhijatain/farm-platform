# WhatsApp Cloud API integration — Secure account-link foundation

**Status:** Signed Meta callbacks, metadata-only inbox, Firebase-authenticated
farmer linking, explicit service-message consent, STOP/unlink, and language
preferences. **No chatbot, outbound sending, media processing, or farm data
queries through WhatsApp yet.**

## Configuration

Register the app and number with the official Meta WhatsApp Business Cloud API.
For the FastAPI service, set:

```dotenv
WHATSAPP_VERIFY_TOKEN=<unique-high-entropy-secret>
WHATSAPP_APP_SECRET=<Meta App Secret>
WHATSAPP_PHONE_NUMBER_ID=<numeric number ID from WhatsApp API Setup>
```

Set the callback URL to
`https://<your-https-api>/api/v1/webhooks/whatsapp`
and subscribe to **messages**. Both values must remain private server-side
secrets. Use HTTPS; never configure them as frontend `VITE_` variables.
With either secret absent, the respective verification endpoint fails closed.
The numeric phone number ID is additionally required for linking and is
checked against Meta's signed inbound message metadata.

Apply the migration to your development database:

```bash
cd services/api
uv run alembic upgrade head
```

GET verification returns Meta's challenge **only** if mode and verify token
match. POST verifies `X-Hub-Signature-256` using the raw body and App Secret,
then writes only validated message IDs, sender IDs, phone-number IDs, message
type and arrival time to PostgreSQL. Re-delivered messages are ignored by a
unique constraint. No farmer message text, voice clip, media ID or geolocation
is stored. Unknown/status-only callbacks are acknowledged without an action.

## Link a test farmer (requires a real signed inbound WhatsApp event)

1. Sign in to Farm Platform using Firebase **phone authentication**.
   Requests to the following three HTTP endpoints need the Firebase ID token
   as an Authorization: Bearer token. Other users cannot link your account.
2. `POST /api/v1/whatsapp/link/start` with:

   ```json
   {"consent": true, "preferred_language": "pa"}
   ```

   Language codes: `pa` Punjabi, `hi` Hindi, `en` English. Consent is
   for WhatsApp **service messages**, not marketing. The API returns a random
   one-time 20-character code and expiry (10 minutes). Only a SHA-256 hash
   is stored; do not paste the code into logs, screenshots or support tickets.
3. From the same phone number verified by Firebase, send
   `LINK YOUR_20_CHARACTER_CODE` to the configured WhatsApp business number.
   The signed webhook verifies the sender's actual WhatsApp ID matches the
   Firebase-verified E.164 phone number and Meta's receiving phone ID matches
   `WHATSAPP_PHONE_NUMBER_ID`. Inbound signed messages are deduplicated by
   Meta message ID. The code is consumed atomically with the inbox insert.
4. `GET /api/v1/whatsapp/link` shows `linked`, `pending`, `unlinked`
   or `revoked`, language and masked sender digits.
5. To revoke: `DELETE /api/v1/whatsapp/link` while Firebase-authenticated,
   or send `STOP` from the linked WhatsApp number. Both immediately clear
   consent and binding. If the verified Firebase phone number changes,
   linked access and pending codes are revoked automatically.

The signed-in Farm Platform web dashboard now includes a **WhatsApp linking
screen**. Click the **WhatsApp chat icon** near the bottom of the left rail,
choose a language, consent, generate a code and copy the LINK command. It
uses Firebase authentication via the existing API client; codes exist only
in transient React state and are not persisted in the browser. Status can
be refreshed manually or automatically during the pending phase. The full
procedure is documented in `apps/web/README.md`.

**Important limitation:** Meta reports that an unpublished app can receive
test webhooks from the dashboard, but not necessarily live incoming farmer
messages. Dashboard samples use synthetic numbers: they may create metadata
in the inbox but **cannot** link a real Firebase farmer unless the signed
sender matches that farmer's verified number. Complete end-to-end phone
linking requires permitted real inbound delivery and further Meta setup.
Do not mark production onboarding ready merely because a sample returned 200.

No farmer chat body or LINK secret is persisted or logged by the app. Only
the inbound message envelope is stored. The `whatsapp_links` table records
user ID, maskedable WhatsApp sender identifier, consent timestamp, preferred
language, one-time hashed challenge and revocation state. Existing farms,
fields, crop cycles, activities and media stay in their canonical tables.

This deliberately stops short of responding to farmer requests. Do not
promote this to a farmer-facing service until the durable outbox, session
rules, and language menus are implemented and tested.

## Next milestones

1. Durable processing/outbox with correct Meta 24-hour session handling.
2. Punjabi/Hindi/English numeric menus and authorized farm/field selection.
3. Deterministic activity capture with explicit field/date confirmation.
4. Plain-language field summaries and geotagged scouting.

See `docs/WHATSAPP_FIRST_PRODUCT.md` and `TODO.md`.
