# WhatsApp-First Farmer Interface — Product and Architecture Plan

**Status:** Planned; no WhatsApp code exists on `main` or PR #11. Last reviewed 2026-10-15.
**Strategy:** Treat WhatsApp as the everyday farmer interface, and the existing web interface as the deep-analysis, administration, map-editing and agronomist workspace. The product assumption that ~80% of farmers may prefer WhatsApp is a **target/hypothesis**, not a measured adoption percentage. Validate in a pilot.

**Primary workflow:** capture actual farmer observations and activities → run the existing owner-authorized farm services → return field-specific, simple-language reports → collect field verification/corrections → learn over seasons. The same `farm_id`, `field_id`, `crop_cycle_id`, media and activity rows serve both interfaces; do not introduce a second farm database.

## What farmers can do (MVP first, richer capabilities later)

| Action in WhatsApp | Farmer-facing experience | Backend existing today | Status / prerequisite |
|---|---|---|---|
| Welcome, language selection and consent | “1 ਪੰਜਾਬੀ / 2 हिंदी / 3 English”; allow change at any time | Firebase user records, phone field | New onboarding and explicit WhatsApp consent needed |
| Register or link a farm | Verify/link account, choose or name an existing farm | Users/farms/seasons/fields/crops | New secure identity binding; phone number alone is not enough |
| Add/select a field | Choose saved field using numbered menu; send pin as approximate location | Field polygon and area | **Location pin is not a polygon**. Use secure one-time map link/WhatsApp Flow or assisted entry to draw/verify a boundary |
| Start/describe a crop | Crop, variety, sowing/transplant date and expected harvest | Crop cycles | New guided chat/Flow and confirmation |
| Record irrigation, fertilizer or crop work | “Aaj kheth me paani diya” → ask which field, when, how long → confirm | Field activities with details | New intent parsing and deterministic write path |
| Send a photo or a GPS point | “I saw yellow leaves here” plus photo/location; show issue ID and follow-up | Media uploads and activity links | New scouting-point schema and consent/media ingestion |
| Send a voice note | Punjabi/Hindi speech → show transcript for confirmation → apply same structured workflow | No ASR/audio conversational channel | Optional in early rollout, language-accuracy tests essential |
| Ask “How is my field?” | Very short field summary: latest *usable* dated satellite signal, changes, rain, stage, what to inspect | Satellite, weather, growth stages | New verified report composer; no unsupported diagnosis |
| Request an image map/report | Small readable annotated PNG map, optionally PDF, with accessible text alternative | TiTiler rasters, API | New report rendering and delivery, signed expiring links |
| Ask “Did it rain?” or “Should I water?” | Modeled past rain / forecast labeled as such. Explain irrigation decision needs soil/field checks | Weather, irrigation logs | Explain measured vs modeled; no automatic precise water dose |
| Receive notifications | “New satellite view available”, weather warning, scouting reminder | Ingestion status, weather | Opt-in per notification type, approved templates, quiet hours and costs |
| Track costs, production and seasons | Harvest summary, expenses when available, simple yield comparison | Yield recording present; costs not built | Link to future T39–T42 |
| Talk to a person | “ਕਿਸਾਨ ਸਹਾਇਤਾ / किसान सहायता / Help” | No operator console yet | Escalation to staff/phone with clear fallback |

## Sample conversation (illustrative — NOT a real field finding)

### Punjabi (Gurmukhi)

**Farmer:** “ਮੇਰੇ ਝੋਨੇ ਦੇ ਖੇਤ ਦੀ ਕੀ ਹਾਲਤ ਹੈ?”

**Farm assistant:**
> “ਤੁਹਾਡੇ ਝੋਨੇ ਦੇ ਖੇਤ ਦੀ ਨਵੀਂ ਵਰਤਣਯੋਗ ਸੈਟੇਲਾਈਟ ਤਸਵੀਰ 29 ਸਤੰਬਰ ਦੀ ਹੈ।
> ਪਿਛਲੇ 3 ਦਿਨਾਂ ਦਾ ਮਾਡਲ-ਅਧਾਰਿਤ ਮੀਂਹ ਲਗਭਗ 17 ਮਿ.ਮੀ. ਸੀ।
> ਤਸਵੀਰ ਵਿੱਚ ਇੱਕ ਹਿੱਸੇ ਵਿੱਚ ਬਦਲਾਅ ਦਿਖਦਾ ਹੈ, ਪਰ ਇਸ ਦਾ ਕਾਰਨ ਪੱਕਾ ਨਹੀਂ।
> ਉਸ ਥਾਂ ਜਾ ਕੇ ਫੋਟੋ ਭੇਜੋ ਤਾਂ ਅਸੀਂ ਰਿਕਾਰਡ ਵਿੱਚ ਜੋੜ ਸਕੀਏ।
> 1 — ਨਕਸ਼ਾ, 2 — ਕੰਮ ਦਰਜ ਕਰੋ, 3 — ਮਦਦ”

### Hindi

**Farmer:** “मेरे धान के खेत में क्या हो रहा है?”

**Farm assistant:**
> “आपके धान के खेत की पिछली उपयोगी सैटेलाइट तस्वीर 29 सितंबर की है।
> उस समय से पहले तीन दिनों में मॉडल के अनुसार लगभग 17 मिमी बारिश हुई थी।
> तस्वीर में एक हिस्से में बदलाव दिख रहा है, लेकिन कारण पक्का नहीं है।
> कृपया उस जगह जाकर फोटो भेजें।
> 1 — नक्शा, 2 — खेत का काम दर्ज करें, 3 — मदद”

Use *verified data bound to the actual field* instead of these illustrative figures. Avoid unexplained “NDVI 0.63”, “VH -14.89 dB”, “82% healthy” or exact diagnoses. A drill-down may offer technical numbers upon request.

## Language and accessibility rules

1. Prioritize **Punjabi (Gurmukhi), Hindi and English** for the initial Punjab/Haryana pilot. Consider Roman Punjabi/Hinglish input; add region-specific languages only after vocabulary testing (Marathi, Gujarati, Bengali, Tamil, Telugu etc.). Haryana dialect options can follow actual user research.
2. Remember preferred **spoken language** and **written script** separately. Do not assume a user who speaks Punjabi reads Gurmukhi fluently. Short choices and buttons must work without reading paragraphs.
3. Keep messages ~3–6 short lines, one action/question per turn, with local crop vocabulary such as ਝੋਨਾ/धान, and explicit date/context.
4. Turn technical metrics into verified plain statements (“vegetation signal decreased compared with the earlier comparable image”), with “what we know / what we don't know / what to do next.”
5. Reply with numbered commands as fallback if interactive message controls or a Flow are unavailable.
6. Support images, low-resolution static maps and optionally audio/read-aloud summaries. Never pretend a voice transcription is certain; show a confirmation especially for quantities, dates and chemical names.
7. Standardize units in local convention, acres, mm rainfall, °C, rupees; convert and label correctly. Support old and local crop/field aliases, but require disambiguation before any write.
8. Keep a human-help path and a way to exit/STOP even if the natural-language system fails.
9. Avoid using generative AI to invent fertilizer doses, disease diagnoses, rain observations, yield or agronomic references. If source evidence is inadequate, say so.

## Proposed architecture (one backend data model)

```text
Farmer WhatsApp
   ↕
Meta WhatsApp Business Platform — Cloud API
   ↕ HTTPS GET verification + signed POST webhooks
FastAPI WhatsApp gateway (new channel adapter)
   ├─ verify X-Hub-Signature-256 and webhook challenge
   ├─ normalize text/buttons/list/Flow/image/audio/location/status
   ├─ inbound event idempotency + audit, respond to Meta promptly
   └─ durable job/outbox queue (retry + dead-letter)
   ↕
Conversation state machine + optional transcription/translation assistant
   ├─ language + accessible menus
   ├─ authorized account / farm / field / crop selection
   ├─ typed intent and explicit confirmation before database writes
   ├─ service orchestrator (only *existing owner-authorized* core APIs)
   ├─ fact-checked report composer with timestamps and sources
   └─ human escalation
   ↕
Existing Postgres/PostGIS, satellite worker, weather, growth stages,
GCS media, TiTiler, activity and yield services
   ↕
Outbound dispatch with opt-in, Meta template/window validation,
deliverability tracking, retries, rate and spend budgets
```

**Prefer Meta's direct Cloud API** in initial development (already compatible with FastAPI). BSPs may improve onboarding/operator tooling, but add fees/dependencies. Cloud API access requires a Meta Business Portfolio, WhatsApp Business Account, business phone number, API app credentials and production setup. Do not use unofficial WhatsApp Web scraping/bot tools.

### Suggested new data structures (proposed, not implemented)

- `whatsapp_identities`: user ID, WABA sender phone ID, WhatsApp recipient ID, verified link state, consent status, created/updated timestamps.
- `whatsapp_conversation_states`: current farm/field/crop, expected answer, language/script, state TTL, handoff state and version (with opt-in).
- `whatsapp_inbound_events`: unique external message ID, channel, minimal normalized payload, idempotency/deduplication, processing outcome and expiry.
- `whatsapp_outbox`: recipient, requested kind, category/template ID, scheduled time, status, attempt count, delivery receipts, error and cost estimate.
- `whatsapp_opt_in_events`: scope, channel, source, explicit permission, notice version, opt-out, quiet hours.
- `whatsapp_report_requests` / `whatsapp_feedback`: field-scoped report request, rendered artifacts, what was checked and farmer corrections.
- New geotagged scout observations belong in canonical field/scouting tables, **not only** in WhatsApp message logs.

Design retention, encryption, access control, redaction, deletion/export paths and local legal compliance before storing farmer voices, photos and precise field locations.

### Safety and reliability rules

- **Identity:** never authorize access merely because a WhatsApp message contains a user ID or field name; link with verified account flow (short-lived nonce/OTP and explicit user approval), reauthorize on phone change, restrict farm/field membership.
- **Authenticity:** challenge verify, HMAC signature-check the raw POST body, HTTPS, secret manager rotation, replay limits, dedicated webhook credentials, idempotent message IDs, and do not let late/retried webhooks write duplicate activities.
- **Write safety:** explicit field/date/quantity/crop confirmation before creating/altering activities or field records; use deterministic validated schema and permission checks. LLM can interpret/translate, but cannot directly execute arbitrary SQL or make up API results.
- **Reporting:** use server queries for dates, satellite quality, uncertainty, spatial resolution, crop context and source. Never turn “no suitable scene” into “healthy crop.” Send map with caption + text summary.
- **WhatsApp rules:** collect opt-in before business outreach; STOP/unsubscribe; approval of message templates outside the 24-hour service window; keep consent by subject, delivery receipts, template category, language and Meta review status.
- **Pricing:** calculate monthly projections using **current official Meta rate cards and category definitions**, not hard-coded 2024/2025 price articles. Count delivered messages, templates, audio/media and optional AI processing/translation as distinct expenses; enforce per-farmer/day budgets.
- **Human escalation:** “human help” must route to an actionable operator queue/contact, not a dead-end button. Do not silently present a generated answer as a human agronomist.
- **Privacy:** opt-in/out, published privacy notice, minimum collection, deletion/export, permission checks on signed report URLs, access logs and no cross-farm leakage.
- **Anti-abuse:** input validation, request size and audio duration limits, media malware checks, rate limits, allowlist for app actions, escaping untrusted model/media content.
- **Evaluation:** test dialects, mixed scripts, literal negation (“did NOT irrigate”), ambiguity (“kal”), quantities (“2 bags”), unsafe pesticide wording, multiple fields with the same name, older satellite scenes and missing weather, phone reassignment and lost account access.

## MVP: first useful WhatsApp release

**MVP acceptance workflow:** a pilot farmer sends “Hi”, selects Punjabi/Hindi, consents, verifies a field, asks for their latest field weather/satellite summary, records an irrigation activity, gets a read-back confirmation, sends an image with location for scouting, requests a shareable field report, and reaches support. All outputs reflect the canonical web data, not a separate messaging datastore.

**Sequence:**

1. Register Meta production/test assets and provider credentials; build secure webhook, idempotent storage and outbound text replies.
2. Verified identity/farm link, language/script preference, opt-in/out, deterministic numeric-button menus and conversation state.
3. Read-only field and weather/last-satellite summaries; constrain outputs to actual data and clearly dated context.
4. Two-way create-activity workflow with confirmations; add phone-photo + location scouting and basic map report link.
5. Add approved templates, opt-in scheduled reports, worker delivery tracking and human escalation.
6. Add voice notes, speech output, flows and richer multilingual reports once text MVP is tested.

**Pilot metrics to track:** WhatsApp vs web adoption (test the 80% hypothesis), successful farmer-onboarding share, percent of intents completed, language correctness by native speakers, accidental write rate (target zero), farmer corrections, delivery failure, cost per active farmer, consent/opt-out rates, support escalation and report usefulness.

## Reference rules and official links

- [Meta Cloud API overview/official Postman collection](https://www.postman.com/meta/whatsapp-business-platform/documentation/wlk6lh4/whatsapp-cloud-api)
- [Official Business Messaging Policy](https://business.whatsapp.com/policy) (24-hour customer service window; consent; templates; human escalation; privacy)
- [Official pricing and categories](https://business.whatsapp.com/products/platform-pricing) (recheck before each deployment and budget)
- [Official Meta WhatsApp Flows collection](https://www.postman.com/meta/whatsapp-business-platform/overview)

The WhatsApp channel should unlock the capabilities in [TODO.md](../TODO.md), especially T01–T12 (field change summary, report, scouting and evidence). It is an **interface and orchestration layer**, not a substitute for sound geospatial/agrarian validation.
