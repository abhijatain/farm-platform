# WhatsApp Cloud API integration — Real phone linking and interactive farm menus

**Status:** Real Firebase SMS login, two-channel WhatsApp linking, explicit
service-message consent, STOP/unlink, and Punjabi/Hindi/English **interactive
menus** for the authorized user's existing farms, seasons and fields.
Message dispatch requires an explicitly enabled, separately running outbox
worker and a Meta WhatsApp business account permitted to send messages.
**No AI, media, agronomic advice, farm edits or unsolicited campaigns.**

## Configuration

Register the app and number with the official Meta WhatsApp Business Cloud API.
For the FastAPI service, set:

```dotenv
WHATSAPP_VERIFY_TOKEN=<unique-high-entropy-secret>
WHATSAPP_APP_SECRET=<Meta App Secret>
WHATSAPP_PHONE_NUMBER_ID=<numeric number ID from WhatsApp API Setup>
WHATSAPP_BUSINESS_DISPLAY_PHONE=<public E.164 WhatsApp business number, +...>
WHATSAPP_ACCESS_TOKEN=<Meta Cloud API sending access token>
WHATSAPP_GRAPH_VERSION=v26.0
WHATSAPP_OUTBOUND_ENABLED=false
```

Keep `WHATSAPP_OUTBOUND_ENABLED=false` while the WABA is blocked or when
testing without approved outbound messaging. App Secret verifies signatures;
access token is a separate credential used only by the outbox worker. They
must never appear in `apps/web/.env` or screenshots.

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

This responds only to explicitly linked farmers asking for read-only
farm/season/field menus, and only within Meta's service conversation window.
Do not promote it to production until the Meta account restriction has been
resolved and end-to-end delivery, retries, consent and privacy have been
validated using a legitimate business phone number.

## Sign in using your real mobile number

Firebase phone login already exists. It is not an OTP implementation we
control: Firebase must actually send and verify the SMS. Set
`VITE_FIREBASE_TEST_PHONE_AUTH=false` in **apps/web/.env**, restart Vite,
sign out of the development user (such as `+919999999999`), and sign in
with the real WhatsApp-capable mobile number in E.164 format (`+91...`).

In the **Firebase Console → Authentication**, enable the Phone provider,
allow the destination country in the SMS region policy, and configure
an authorized web authentication domain and the required billing/SMS quota.
Follow Firebase's latest instructions for real-phone web verification,
reCAPTCHA and HTTPS domains. Some newer Firebase projects do not authorize
localhost by default; a suitable authorized HTTPS development domain may be
needed for genuine SMS authentication. Do not disable app verification for
a real phone.

**Important user ownership consequence:** Firebase creates a **different user
record** for the new verified phone. Any farms owned by a fictional seeded
user stay owned by that original user and therefore are not visible in
WhatsApp. Create farms under the real user for testing, or explicitly migrate
ownership with an authorized administrative process. Never automatically
merge accounts based only on a phone claimed in a chat.

## WhatsApp interactive menu

Once the real sender matches the Firebase-verified phone, reply from that
number to the configured WhatsApp business number:

```text
LINK <one-time-20-character-code>
```

A **signed live** LINK webhook consumes the code and enqueues a welcome list.
A signed inbound `MENU` or `HELP` displays the main interactive list:

- My farms
- My seasons
- My fields

Select a farm in the interactive list, then see its seasons or fields.
Select a season/field to see its name and parent farm (plus season status
and starting date). Text commands `1`, `2`, `3`, and `MENU` also work.
Each row ID is rechecked against the linked Firebase **owner** before the
canonical PostGIS farm/season/field data is read. Lists paginate when there
are many entries. Read-only only. A signed `STOP` clears consent and binding.

Meta's ordinary service/interactive messages are permitted within the
customer-service conversation window initiated by the user's inbound
message. This gateway uses the **signed incoming message's timestamp** and
a 15-minute safety margin: if no valid timestamp or the window has expired,
no new outgoing message is queued. Business-initiated notification templates,
marketing and arbitrary outreach are intentionally **not implemented**.

### Outbound worker — run separately

After obtaining an approved Meta business account and a valid sending
token, set `WHATSAPP_OUTBOUND_ENABLED=true` privately on the server, then
in an additional terminal:

```bash
cd services/api
uv run python -m app.channels.whatsapp.outbox --loop
```

To process just one queued message:

```bash
uv run python -m app.channels.whatsapp.outbox --once
```

When disabled or missing a sending token, the worker prints `disabled`
and sends nothing. Keep the regular FastAPI process plus ngrok/backend
public HTTPS webhook running separately. The queue and worker survive
ordinary webhook retries and restart and enforce sender/consent checks
before sending. Some ambiguous network failures may lead to duplicate
**read-only** replies if Meta accepts a message but the worker crashes
before recording the receipt. This mechanism must not be used to execute
non-idempotent crop activities.

Useful SQL when debugging local development:

```sql
SELECT status, attempts, last_error, created_at, sent_at
FROM whatsapp_outbox ORDER BY created_at DESC LIMIT 10;
```

Do not print `payload`, `recipient_wa_id`, secret tokens, or private message
contents into public screenshots.

### Offline smoke tests (does not contact Meta)

```bash
cd services/api
uv run alembic upgrade head
uv run --with pytest python -m pytest -q tests/test_whatsapp_menus.py tests/test_whatsapp_linking.py
```

The tests construct signed synthetic WhatsApp events, verify menu schema
and owner authorization with two different farmers, exercise the durable
outbox and verify that delivery is disabled by default.

**Meta restriction:** Your developer dashboard previously displayed
`Account closed` for the WhatsApp Business Account. A closed/restricted
WABA cannot be treated as a live end-to-end test destination. Request review
in Meta Business Support and do not turn on actual outbound sends until the
account/phone has been reinstated or otherwise officially authorized.
Passing the simulated tests does not remove this external blocker.

## Next milestones

1. Production Meta account review, signed live-delivery validation and monitoring.
2. Read-only weather and dated satellite summaries in the same verified menus.
3. Deterministic activity capture with explicit field/date confirmation.
4. Media scouting, plain-language reports and delivery-status observability.

See `docs/WHATSAPP_FIRST_PRODUCT.md` and `TODO.md`.
