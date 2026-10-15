# WhatsApp Cloud API integration — Phase 0

**Status:** Meta callback verification and a minimal secure event inbox only. This
release does **not** link farmer identities, respond to WhatsApp messages,
generate farm reports, handle image/audio content or send proactive messages.

## Configuration

Register the app and number with the official Meta WhatsApp Business Cloud API.
For the FastAPI service, set:

```dotenv
WHATSAPP_VERIFY_TOKEN=<unique-high-entropy-secret>
WHATSAPP_APP_SECRET=<Meta App Secret>
```

Set the callback URL to
`https://<your-https-api>/api/v1/webhooks/whatsapp`
and subscribe to **messages**. Both values must remain private server-side
secrets. Use HTTPS; never configure them as frontend `VITE_` variables.
With either secret absent, the respective verification endpoint fails closed.

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

This deliberately stops short of sending messages or interpreting farmer
requests; acknowledged inbound content is **not yet acted upon**. Do not
promote this to a farmer-facing number until the opt-in, identity linking,
outbox, command processing and support flows are implemented and tested.

## Next milestones

1. Verified account/farm linking, consent and preferred language.
2. Durable processing/outbox with correct Meta 24-hour session handling.
3. Punjabi/Hindi/English numeric menus and deterministic activity capture.
4. Plain-language field summaries and geotagged scouting.

See `docs/WHATSAPP_FIRST_PRODUCT.md` and `TODO.md`.
