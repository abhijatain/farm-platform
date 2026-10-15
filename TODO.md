# Farm Platform — Non-Drone Product TODO and Priorities

Reviewed: 2026-10-15. This is the **persistent feature backlog**, ranked for small/medium Indian farms, with rice/wheat/maize and orchards supported as separate crop contexts. No promised timelines or accuracy guarantees. See [verified existing inventory](docs/FEATURE_INVENTORY.md) before calling something “not built.”

**Delivery strategy:** **WhatsApp-first** for everyday farmer conversations, input collection, weather/satellite summaries, scouting and reports; web for detailed maps and advanced work. See [WhatsApp architecture and experience](docs/WHATSAPP_FIRST_PRODUCT.md). The assumption that 80% of users will prefer WhatsApp is a pilot target, not a measured fact.

**Scope:** Include non-drone functions inspired by Agremo, OneSoil, EOSDA, CropX, xarvio, PIX4Dfields, Taranis and Climate FieldView. **Exclude all drone acquisition and drone-dependent individual plant/weed counting, drone orthomosaics and drone spray flight planning for now.** Manually entered counts and ground-level/phone photos are allowed, but must not be described as satellite counts.

## Scoring rubric and release gate

- **I/10 — importance:** practical expected value to farmer/adviser (10 highest). These are judgment-based use-case rankings, not proof of ROI.
- **F/5 — feasibility:** estimated ability to build useful, defensible output from available or obtainable data (5 highest), not predicted model accuracy.
- **E — engineering effort:** S = few days; M = ~1–2 weeks; L = ~3–6 weeks; XL = multiple months. Broad rough estimates for focused implementations; data collection/validation may take longer.
- **P0** = build next; **P1** = next core milestone; **P2** = medium-term agronomy; **P3** = advanced/optional; **P4** = specialist hardware/machinery.
- A task is “done” only with tested backend/UI, provenance, error states, owner access, documentation and realistic field verification. Never mark unsupported output “healthy,” “diseased” or “water stressed.”
- Precondition for any alert/prescription: validate against local field observations and hold out fields/seasons; record false positives, false negatives, sensor/time coverage, limitations and appropriate uncertainty.

## Active, separate PR (not yet on main)

- [ ] **R01 — Evaluate PR #10 locally, then merge or revise.** Farmer-confirmed growth-stage radar variation screening; no crop-health diagnoses. It currently often has insufficient evidence on short histories. **I 8 · F 3 · E S** for review. https://github.com/abhijatain/farm-platform/pull/10
- [ ] **T01 — Two-pass descriptive radar changes regardless of confirmed stage** (**P0 · I 10 · F 5 · E S**): latest minus previous valid *same-orbit* VH/VV in dB and RVI in index units, with gap days, coverage, acquisition date, weather and farm activity; always describe, never diagnose. Must show a result with just two comparable dates. Do NOT weaken R01 anomaly gates to accomplish this.

## P0 — Field usefulness and evidence loop (build first)

- [ ] **T02 — Replace the empty Report tab with a complete field report** (**I 10 · F 5 · E M**): crop, field area, current/last usable observation, source and valid-pixel quality, recent NDVI/NDMI/radar changes, anomaly acreage, weather/rain, confirmed stage, activities and next scouting steps. Label missing facts. Add export to PDF/CSV later in T44.
- [ ] **T03 — Geotagged field scouting and issue reports** (**I 10 · F 5 · E M**): tap on a map/anomaly zone; record GPS point, timestamp, reason, severity as observed by farmer, notes and ground-level photo/video; connect to crop cycle and satellite acquisition.
- [ ] **T04 — Scouting workflow: investigate → verify/reject → follow-up** (**I 10 · F 5 · E M**): create a task from a mapped zone, assign a status, revisit and mark resolved. Keep remote signal and field observation separate; record whether a false positive occurred.
- [ ] **T05 — Pixel/resolution suitability warnings for small fields** (**I 10 · F 5 · E M**): show native bands' 10/20/30 m scale, effective valid independent pixel count, edge/mixed-pixel limitations, clouds and geometry quality. Suppress false precision when a field has too few usable pixels.
- [ ] **T06 — Unified field findings rather than disconnected raw indices** (**I 10 · F 4 · E M**): summarize what changed, where, amount/area, observation date, supporting/conflicting signals and proposed scouting action; distinguish verified vs suspected vs data unavailable.
- [ ] **T07 — Historical versus present-weather period clarity** (**I 8 · F 5 · E S**): if viewing a completed rice season ending Oct 8, label last-seven-days as relative to Oct 8, not today; do not show unrelated “next six days” forecasts. Show completeness and timezone clearly.
- [ ] **T08 — Multi-day field anomaly history and spatial persistence** (**I 9 · F 4 · E L**): extend existing pairwise new/persistent/resolved overlaps into 3+ acquisitions with multi-date polygons, dates, acreage, counts and stable tracking; require comparable source/index/resolution.
- [ ] **T09 — Crop/stage-aware vegetation index interpretation** (**I 9 · F 4 · E M**): context and suitable index choices for establishment/tillering/flowering/maturity (e.g. SAVI/MSAVI early, NDRE chlorophyll-related later). Show caveats; never map one index directly to a diagnosis.
- [ ] **T10 — Weather and satellite data completeness dashboard** (**I 9 · F 5 · E M**): visible “available, missing, cloud-skipped, not comparable, stale” by sensor/date. Include model/reanalysis/forecast provenance, retry visibility and refresh status.
- [ ] **T11 — Formal source-of-truth & review rules for alert UX** (**I 10 · F 5 · E M**): versioned rules, confidence/coverage levels, suppress unsupported findings, store farmer confirmation outcomes; test zero rainfall != missing rainfall and “not flagged” != “healthy.”
- [ ] **T12 — Weather season context** (**I 8 · F 5 · E S**): accumulated and 7/14/30-day rain, rainfall anomalies against a documented reference (when available), heat days, GDD and ET0 timelines aligned to crop activity dates. Present estimates vs observations.

## P1 — The strongest OneSoil/EOSDA-like non-drone modules

- [ ] **T13 — Multi-year historical productivity/variability zones** (**I 10 · F 3 · E XL**): ingest 5–10+ suitable years, mask clouds and compare similar phenological windows; create repeated low/medium/high *relative vegetation performance* zones with stability score and acreage. Do NOT call zones measured yield or absolute soil fertility.
- [ ] **T14 — Crop- and stage-aligned historical comparisons** (**I 9 · F 3 · E L**): compare rice at tillering this year vs prior rice/tillering periods, not unrelated dates or crop rotations. Include variability and uncertainty, and separate short-history fields.
- [ ] **T15 — Normalized/contrasted NDVI and within-field deviation maps** (**I 8 · F 5 · E M**): show subtle within-field differences and “relative to field” not hard-coded healthy colors. Apply stable scaling and guard against sparse small plots.
- [ ] **T16 — Management zones and scouting/sample recommendations** (**I 9 · F 4 · E L**): derive interpretable zones from historical layers and verified issues; area, centroid, visit points and suggested soil-sample locations, not fertilizer doses.
- [ ] **T17 — Soil laboratory/sample records** (**I 10 · F 5 · E M**): geolocated depth, date, sampling method, pH, texture, EC, organic carbon, N/P/K with units and lab provenance; support manual entry/CSV and comparison across seasons.
- [ ] **T18 — Regional soil property maps** (**I 8 · F 3 · E L**): optionally integrate openly licensed gridded soil data, show resolution/uncertainty and never replace a measured soil test with a coarse predicted map.
- [ ] **T19 — Terrain/elevation/slope/drainage context** (**I 8 · F 4 · E L**): DEM-based slope, catchment and flow-path overlays where resolution is appropriate; explicitly flag flat/small fields where DEM error exceeds signal.
- [ ] **T20 — Rice ponding/flooding/waterlogging *candidate* maps** (**I 10 for rice · F 2 · E XL**): explore same-orbit Sentinel-1 change, optical water indices, rain and field reports; detect ambiguous potential standing water/dry-down, test against ground observations before alerts.
- [ ] **T21 — Field investigation layers: severity, affected acreage, reference date and persistence** (**I 10 · F 4 · E L**): make existing field-relative anomaly geometries inspectable with polygon ID, recent history, uncertainty and resolution; allow flagging false positives.
- [ ] **T22 — Better crop-stage tracking (BBCH-style where suitable)** (**I 9 · F 3 · E L**): crop/cultivar/regional phase templates, visual descriptions, farmer edits and GDD models with upper/base temperature, photoperiod and local validation; don't relabel current broad day-based estimates as BBCH-confirmed.
- [ ] **T23 — Manual pest, weed, disease symptom and stand-count observations** (**I 9 · F 5 · E M**): record species/symptom, severity, photos and manual quadrat count. No satellite-based individual weed identification, no invented plant counts.
- [ ] **T24 — Ground-photo review / optional phone-image symptom triage** (**I 8 · F 2 · E L**): if added later, allow reviewable photo categories with uncertainty and expert/field confirmation. No autonomous pesticide recommendation.
- [ ] **T25 — Historical, current and field-observed data in one geospatial event timeline** (**I 9 · F 4 · E M**): align NDVI, radar, rainfall, stage transitions, spraying, irrigation and scouting outcomes with precise provenance.
- [ ] **T26 — Orchard/perennial crop-specific field context** (**I 8 · F 3 · E L**): avoid applying rice/wheat seasonal phenology and maturity assumptions to trees; support pruning, fruiting cycles, perennial ground cover and orchard management zones.
- [ ] **T27 — Soil and productivity stability score for sample planning** (**I 8 · F 3 · E L**): recommend repeatable sampling spots and management zones from persistent field differences, then test correspondence to real soil lab results.

## P2 — Agronomic decision support (modeling + validation required)

- [ ] **T28 — Simple crop-water balance** (**I 10 · F 3 · E L**): use rain + recorded irrigation + stage-based ETc (crop coefficient × ET0) + soil holding capacity; track uncertainty; never label this sensor-measured root-zone moisture.
- [ ] **T29 — Root-zone soil moisture estimates and wet/dry risk context** (**I 9 · F 2 · E XL**): calibrated water-balance/model estimates, optionally enhanced by soil sensors and SAR, with depth range and confidence; clearly distinct from NDMI or surface wetness.
- [ ] **T30 — Rice-specific water management / alternate wetting and drying context** (**I 10 for rice · F 2 · E XL**): support recorded flood depth, drainage events and stage-related flood sensitivity, rain forecasts and sensor/manual verification before any irrigation guidance.
- [ ] **T31 — Explainable irrigation planning suggestions** (**I 10 · F 3 · E L**): crop/stage soil-water deficit ranges, forecast rain, irrigation history, pump constraints and a user-confirmable recommendation; validated thresholds before automatic notices.
- [ ] **T32 — Heat, cold, excess rain and spraying-weather risk windows** (**I 9 · F 4 · E M**): temperature, humidity, wind and rain forecast with source/timezone; stage-specific warnings only where backed by agronomic literature.
- [ ] **T33 — Crop disease/pest pressure risk models** (**I 9 · F 2 · E XL**): start with clearly-defined rice/wheat disease-weather relationships and independently validated thresholds; show “conditions favorable,” not “disease detected.”
- [ ] **T34 — Fertilizer/N-P-K planning based on actual soil tests and crop targets** (**I 9 · F 2 · E XL**): stage, expected yield, lab results, soil pH/EC, previous inputs and regional best practices; require agronomist-reviewed rates.
- [ ] **T35 — Crop-stage-aware optical + SAR screening calibrated with ground truth** (**I 9 · F 2 · E XL**): extend PR #10 exploratory radar signals using crop/cultivar/site/stage baselines, weather, optical confirmation, persistence and quantified false-positive rates.
- [ ] **T36 — Spatial SAR change/anomaly polygons with uncertainty** (**I 8 · F 2 · E XL**): native-resolution radar change masks and connected zones for matched geometry; avoid using optical NDVI thresholds for SAR.
- [ ] **T37 — Biomass proxy/relative canopy development maps** (**I 7 · F 3 · E L**): infer relative canopy signal from satellite indices and calibrated phenology, not tonnes of biomass without field samples.
- [ ] **T38 — Trained crop yield forecasting with intervals** (**I 9 · F 2 · E XL**): use many *measured* harvest outcomes, crop, weather, phenology and satellite histories; expose model version and backtested error by region/crop; do not present arbitrary “97% accuracy.”
- [ ] **T39 — Structured fertilizer, chemical and irrigation logs** (**I 9 · F 5 · E M**): normalize dose, concentration, units, products, treated area, method, costs, operator and irrigation volume/depth; build on existing flexible activity details.
- [ ] **T40 — Seasonal costs, revenue and net margin** (**I 9 · F 5 · E M**): input/labor/energy/irrigation expenses, harvest revenue, net profit per crop/acre and provenance; existing selling value alone is not profit.
- [ ] **T41 — Multi-season crop/field comparisons, harvest benchmarking** (**I 9 · F 4 · E L**): compare measured yield, input cost, weather, management and remote signals only for sufficiently comparable seasons.
- [ ] **T42 — Field trials and intervention assessment** (**I 8 · F 4 · E L**): treatment/control zones, baseline observations, ground-truth outcomes and confounders; report uncertainty rather than causal effects from before/after alone.
- [ ] **T43 — Crop protection timing assistant** (**I 8 · F 3 · E L**): wind, rain, forecast, stage, recorded pest scouting and product label restrictions; user approval required; not blanket pesticide advice.

## P3 — Product workflows, reports, scale and optional services

- [ ] **T44 — Downloadable, shareable field reports and geospatial exports** (**I 9 · F 5 · E M**): PDF, CSV and geojson with index legend, area, source date, confidence, weather and ground-truth notes. Signed links/permissions for sensitive farm information.
- [ ] **T45 — Mobile-first/offline field scouting and sync** (**I 9 · F 4 · E L**): cache a field boundary/task and pending notes/photos when disconnected; conflict resolution and upload/retry; a PWA can precede a native mobile app.
- [ ] **T46 — Personalized, user-configurable alerts** (**I 9 · F 3 · E L**): imagery ready, stale data, confirmed stage tasks, forecast weather warnings and verified persistent changes; avoid frequent unvalidated crop-disease alerts.
- [ ] **T47 — Agronomist/team role and delegated access** (**I 8 · F 4 · E L**): owner/invite-only field access, scoped roles, auditing, review and explicit consent for sharing farm data.
- [ ] **T48 — Management-history-linked evidence scoring and learning** (**I 9 · F 3 · E L**): record observed causes, resolutions and harvest outcomes; use these to evaluate model/alert performance across seasons rather than automatically self-labeling satellite anomalies.
- [ ] **T49 — Baseline, model and geospatial-data calibration lab** (**I 9 · F 3 · E XL**): season/crop/field holdouts, disagreement and false-positive dashboards, registered datasets and threshold versions, spatial resolution tests.
- [ ] **T50 — Multi-source environmental context** (**I 7 · F 3 · E L**): optional root-zone proxies, ECOSTRESS thermal data, regional drought indices and credible public datasets, with provenance and observation-date matching.
- [ ] **T51 — Commercial high-resolution satellite imagery adapter (optional)** (**I 7 · F 3 · E XL**): licensing/cost-aware non-drone high-res imagery, separate resolutions and verified analytics. Do not upscale Sentinel-2 and claim real plant-level detail.
- [ ] **T52 — Data cost, licensing, caching and operational observability** (**I 8 · F 5 · E M**): request budgeting, private tiled cache, external API plan limits, retention policy, ingestion lag and cost per field.
- [ ] **T53 — Season/zone management recommendation library** (**I 8 · F 3 · E L**): crop- and stage-aware decision checklists, vetted local agronomic sources, required inputs, confidence and disclaimer; no invented yields or prescriptions.

## P4 — Sensors, precision machinery and advanced agronomy (still NO drones)

- [ ] **T54 — Weather station adapter** (**I 8 · F 4 · E L**): farmer-owned station temperature, rainfall, humidity, wind and data quality; distinguish station observation from gridded model forecasts.
- [ ] **T55 — Soil probe telemetry** (**I 9 · F 4 · E L**): timestamped sensor soil moisture, temperature and EC at specified depths with calibration, units, battery/health and site placement.
- [ ] **T56 — Measured or estimated actual evapotranspiration (ETa) integration** (**I 7 · F 2 · E XL**): separate sensor/remote ETa estimates from reference ET0; validate assumptions and footprint.
- [ ] **T57 — Variable-rate management-zone suggestions** (**I 7 overall; higher on large mechanized farms · F 2 · E XL**): optional zonal recommendations only after soil/field-trial calibration and realistic economics; no universal dose from NDVI color.
- [ ] **T58 — Machine-readable variable-rate prescription exports** (**I 5 for small farms, 9 for mechanized estates · F 3 · E L**): shapefile/GeoJSON/ISOXML formats where appropriate, application-rate units, equipment compatibility, bounds and operator review.
- [ ] **T59 — Equipment and work-order feedback loop** (**I 5 for small farms · F 3 · E L**): record actual tractor/sprayer application positions and rates where connected and compare execution to intended zones.
- [ ] **T60 — Site-specific N/P/K variable-rate validation trials** (**I 7 · F 2 · E XL**): agronomist-approved prescriptions backed by soil/harvest ground truth and economic trials; required before automated application guidance.


## P0–P2 — WhatsApp-first farmer interface (foundation underway)

Treat this as a **primary product interface**, not a push-notification add-on. It reuses the same crop-cycle, field, weather, satellite, activity, media, yield, and future scouting records as the web. The detailed security, architecture, conversation and compliance plan is in [docs/WHATSAPP_FIRST_PRODUCT.md](docs/WHATSAPP_FIRST_PRODUCT.md).

**MVP gate:** A farmer can message our official number, opt in, select Punjabi/Hindi/English, securely link/select a field, ask for a plain-language dated crop report, log an irrigation activity with an explicit confirmation, share a geotagged issue/photo, request help, and stop future proactive messages. Every record is visible from the web app and vice versa. Do not claim this works yet.

| Task | Priority | Importance | Feasibility | Effort | Farmer use case and acceptance criteria |
|---|---|---:|---:|---|---|
| **T61 — Direct Meta Cloud API gateway** | P0 | 10 | 5 | M | Set up WABA, webhook challenge + signature validation, securely stored tokens, typed inbound message parsing and outbound sender. No unofficial WhatsApp Web bots. |
| **T62 — Secure farmer / farm / field account linking** | P0 | 10 | 4 | M | Verified link to current Firebase identity; user can select authorized farms and fields. A sender's phone number, field name or chat text alone cannot grant access. |
| **T63 — Opt-in, STOP, preferences, quiet hours** | P0 | 10 | 5 | M | Store explicit, revocable consent by message type, locale and business identity; opt-out acknowledged and honored; per-farmer schedule. |
| **T64 — Regional languages and plain-language terminology** | P0 | 10 | 4 | M | Punjabi Gurmukhi, Hindi, English first; recognize Roman Punjabi/Hinglish; local vocabulary, date and unit conventions; user-selectable script and language. Native-speaker testing. |
| **T65 — WhatsApp menus, buttons and conversation state** | P0 | 10 | 5 | L | “My field / Weather / Record work / View report / Ask for help”; resume interrupted workflows, ask which field when needed, support numeric replies. |
| **T66 — Dated weather, crop stage and satellite report replies** | P0 | 10 | 5 | M | A short verified summary: last usable satellite date, relative change, modeled vs observed rain, crop stage and suggested scouting action; no NDVI-based disease diagnosis. |
| **T67 — Farm activity capture through chat** | P0 | 10 | 5 | M | Irrigation, fertilizer, planting, harvesting, scouting and crop-protection logs with date, field, quantity and units; read back for confirmation before calling existing activity API. |
| **T68 — Ground photo + location issue reporting** | P0 | 10 | 4 | M | Farmer sends phone photo, location, simple symptom and timestamp; create a geotagged scouting issue linked to the crop/field. Distinguish photo-derived user observation from AI suggestion. |
| **T69 — Field onboarding and boundary verification** | P0 | 9 | 4 | L | Choose a saved field, share location pin for approximate location, and open secure short-lived web map link/assisted Flow for actual polygon boundary. A pin is NOT a field boundary. |
| **T70 — Voice-note understanding with confirmation** | P1 | 10 | 3 | L | Punjabi/Hindi voice clips -> transcript -> verified entities and farm actions; check mixed languages, numerals, “yesterday” and negation before saving. |
| **T71 — Optional spoken audio reports and accessibility** | P1 | 9 | 3 | L | Listen to weather/field report in preferred voice/language, alongside short text and numeric menus; low-bandwidth fallback and quality testing. |
| **T72 — Interactive WhatsApp Flows for structured forms** | P1 | 9 | 4 | L | Onboarding, select crop, record work and scouting; signed/encrypted Meta Flows with numbered-text fallback for unsupported clients. |
| **T73 — Opt-in notifications and scheduled field updates** | P1 | 10 | 4 | L | Weather risk, new satellite view, weekly status and farmer-selected reminder cadence using **approved template messages** outside service window; configurable limit and disable. |
| **T74 — Shareable field reports, maps and PDFs through WhatsApp** | P1 | 10 | 4 | L | Small readable static PNG, PDF when useful, short explanatory text, expiring permission-checked URL, no raw technical chart wall. Builds on T02/T44. |
| **T75 — Grounded crop Q&A, explanations and safeguards** | P1 | 9 | 3 | XL | Questions in farmer's language answered from verified own-field facts and reviewed crop guidance; no invented yield/stress/pesticide rates or assumed sensor readings. |
| **T76 — Confirm, clarify and recover from wrong intent** | P0 | 10 | 5 | M | Verify field, crop, date, units and actions; “Undo/correct” options, no database write from uncertain AI transcript or language guess, clear errors. |
| **T77 — Human support / agronomist escalation** | P1 | 9 | 4 | M | A real agent queue/phone fallback, escalation state and audit, handoff from automated replies, no false pretense that a bot is an expert. |
| **T78 — Privacy, security, media retention and deletion/export** | P0 | 10 | 4 | L | Signed webhook, dedupe, least-privilege access, media scanning, safe storage, log redaction, consent histories, deletion and India-relevant data protection review. |
| **T79 — Durable queue, delivery receipts and cost/rate observability** | P0 | 9 | 5 | M | Webhook quick-ack, idempotent queue/outbox, retries, backoff, Meta template category and delivery accounting, API limits and spend caps. |
| **T80 — Real-farmer multilingual pilot and adoption study** | P0 | 10 | 5 | M | Pilot across literacy levels and crop types; test the “80% WhatsApp” assumption, onboarding rate, task success, native-language comprehension, false actions, report usefulness, cost/farmer and opt-outs. |

### WhatsApp release milestones and dependencies

1. **WA-M0 — Safe channel:** T61–T65, T76, T78–T79. Test webhook signatures, account linking, language menus, consent and STOP with sandbox/test number.
2. **WA-M1 — First useful farmer pilot:** T66–T69 + T80. Data read from actual field/weather/satellite services; confirmation-based activity writes, report and photo issues. Depends on T02/T03/T05/T07 for accurate field findings.
3. **WA-M2 — Accessible scale-out:** T70–T74, T77. Voice, scheduled reports, interactive forms, maps and human support under real Meta message fees/template approval.
4. **WA-M3 — Advanced agronomic assistant:** T75 only when T09, T17, T22, T28–T35 and evidence/ground-truth requirements support reliable crop-specific guidance.

**WhatsApp platform constraint:** Meta's 24-hour response window and approved templates outside that window, explicit opt-in/opt-out, regional template approvals, human escalation and official rate cards are mandatory. Do not price this product assuming free unlimited WhatsApp messages. The farmer's chat conversation is NOT a separate farming database.


## Suggested release sequence

| Sequence | Milestone / outcome | Work IDs | Gate |
|---|---|---|---|
| **0** | WhatsApp-first channel and initial farmer pilot | T61–T69, T76, T78–T80, supported by T02/T03/T07 | Secure identity, consent, local languages, field report and confirmed field activity from chat |
| **1** | Fix missing usefulness: two-pass radar delta, real report, period clarity | R01, T01, T02, T07 | Show useful output on today's 5–7-pass fields without a false anomaly claim |
| **2** | Actionable scouting and data quality | T03–T06, T10–T11, T21, T23 | Farmer can find, visit, photograph and close a mapped issue |
| **3** | Historical intelligence / spatial management zones | T08–T09, T12–T16, T25 | Zones derived with quality filters and repeatability, not made-up yield |
| **4** | Soil, terrain and crop-development context | T17–T20, T22, T26–T27 | Test on real field/soil samples; honest resolution and spatial errors |
| **5** | Rice/water and weather-informed agronomy | T28–T33, T35–T36, T43 | Ground-truth pilot, error bars and conservative alert gating |
| **6** | Inputs, outcomes, field trials and commercial reports | T34, T37–T42, T44–T49 | Observed costs/yield tied to interventions and validation |
| **7** | Optional advanced sources and machinery | T50–T60 | Explicitly opt-in based on devices, field size and economics |

## How the research maps to our backlog (without drones)

| Competitor inspiration | Our non-drone modules |
|---|---|
| **Agremo**: vigor, affected area, biomass, yield and zone prescriptions | T06, T21, T37, T38, T57; **exclude drone stand counting/weed classification** |
| **OneSoil**: contrasted NDVI, historical productivity, scouting, GDD/rain, soil sampling, variable rate, trials | T03–T04, T12–T17, T42, T57–T58 |
| **EOSDA**: crop-specific indices, BBCH, soil/moisture, terrain, risk/scouting | T09, T17–T22, T28–T33 |
| **CropX**: multi-depth soil moisture/EC/temp, root-zone water, irrigation, actual ET | T28–T31, T54–T56 |
| **xarvio**: stage-aware biomass, historical zones, nutrition, crop-protection timing | T13–T16, T22, T32–T43, T57–T60 |
| **Taranis**: verified ground-level crop issues and evidence | T03, T23–T24, T48; **exclude drone/plant-level aerial AI** |
| **PIX4Dfields**: field-management zones and non-drone machine prescriptions | T16, T57–T59; **exclude drone orthomosaics and drone flight outputs** |
| **Climate FieldView**: imagery, scouting, yield and management outcome linkage | T03–T04, T38–T42, T48 |

## Constraints and explicit exclusions

1. **Drone features intentionally deferred:** drone image acquisition, drone orthomosaics, aerial stand and weed counting, drone spot-spraying commands, drone flight planning, high-res drone-derived biomass/yield products.
2. **No pretending ground truth exists:** no exact soil water from NDMI, crop diagnosis from NDVI, measured yield from satellite vigor, or individual-plant detection from 10/20/30 m pixels.
3. **Do not assume all fields can support productivity zones or VRA:** small and mixed pixels, field geometry, limited crop history, cost and machinery compatibility determine utility.
4. **Commercial licensing:** verify terms for imagery, gridded weather, soil datasets, sensor integrations and prescription-machine formats.
5. **Crop specificity:** rice/wheat/maize have provisional phenology templates today; orchard/perennial and other crop models need independent modeling.
6. **No automatic alerts/prescriptions without validation:** pilot with real observations and measurable accuracy, error rates, sensitivity to crop stage and explicit user control.
7. **Existing functionality must be reused, not duplicated:** source-specific NDVI/radar/thermal processing, anomalies, pairwise raster changes, farming records, weather and GDD already exist in the main branch.

## Useful official product references

- Agremo rice: https://www.agremo.com/solutions/rice/
- OneSoil: https://onesoil.ai/en/platform
- EOSDA Crop Monitoring: https://eos.com/user-guide/crop-monitoring/
- CropX: https://cropx.com/
- xarvio: https://www.xarvio.com/
- PIX4Dfields: https://www.pix4d.com/product/pix4dfields/
- Climate FieldView: https://climatefieldview.com/
- Meta WhatsApp Cloud API: https://www.postman.com/meta/whatsapp-business-platform/overview
- WhatsApp messaging policy: https://business.whatsapp.com/policy
- WhatsApp pricing: https://business.whatsapp.com/products/platform-pricing

**Maintenance rule:** When a task is merged, check the box, link its PR, revise the inventory, record any accuracy or deployment limitations, and re-rank unfinished tasks using field experience.