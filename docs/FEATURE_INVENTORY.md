# Farm Platform — Verified Feature Inventory

Last reviewed: 2026-10-15. Source of truth: **main** at commit 3f962949, plus the separately identified open PR #10. This file documents **implemented code**, not a claim of agronomic validation, commercial deployment, or guaranteed data coverage. The companion [TODO.md](../TODO.md) tracks non-drone improvements and new capabilities.

## How to read the ratings

- **Importance (I /10)**: estimated practical value for Indian small/medium farms or their advisers (10 highest). Scores are product judgments, not measured agronomic return.
- **Feasibility (F /5)**: confidence that the core functionality can be useful with its present data source (5 highest). It does **not** imply accuracy of a disease diagnosis.
- **Status**: Live code = implemented on main; Foundation = useful but limited; PR #10 = implemented on unmerged branch; Missing = not implemented.
- Coverage is crop-, location-, date-, imagery-, license- and weather-dependent. A feature can exist while a specific field has no usable observations.

## A. Farm records, field workflow and operations

| ID | Feature on main | Status | I/10 | F/5 | Practical use / important qualification |
|---|---|---|---:|---:|---|
| C01 | Firebase phone login and owner-scoped APIs | Live code | 9 | 5 | Private farm access; not multi-organization agronomist roles |
| C02 | Farm and season management | Live code | 9 | 5 | Keep multiple farms and seasons organized |
| C03 | Map-based field polygon drawing and field area | Live code | 10 | 5 | Bound imagery and compute acres/hectares; map accuracy still matters |
| C04 | MapLibre farm map and selectable imagery layers | Live code | 9 | 4 | Locate within-field variation |
| C05 | Crop cycles with crop name, variety, planting and expected harvest | Live code | 10 | 5 | Interpret satellite events in crop context |
| C06 | Farmer-recorded growth-stage dates and notes | Live code | 9 | 5 | Ground-truth the crop stage; requires farmer entry |
| C07 | Approximate wheat/rice/maize milestone calendars | Foundation | 7 | 3 | Orientation only; not locally validated phenology |
| C08 | Field activities: irrigation, fertilizer and crop-protection inputs | Live code | 10 | 5 | Document actual farming actions; amounts captured in flexible details, not yet normalized agronomy records |
| C09 | Chronological activity/field timeline | Live code | 9 | 5 | Answer what was done and when |
| C10 | Activity-associated before/after satellite metrics and spatial comparisons | Foundation | 9 | 3 | See change after irrigation/fertilizer; **correlation, not causation** |
| C11 | Field image/video uploads, previews and crop/activity association | Live code | 8 | 4 | Evidence and historical photos; NOT geotagged scouting-pin workflow |
| C12 | GCS private objects, signed access, derivative processing and cleanup | Live code | 7 | 5 | Secure scalable media/raster storage |
| C13 | Organized cloud hierarchy and recovery manifests | Live code | 8 | 5 | Recover information without relying entirely on operational DB |
| C14 | Harvest recording: weight, area, grade, moisture, selling price | Live code | 9 | 5 | Ground-truth yield and crop outcomes |
| C15 | Yield per acre and gross estimated harvest value | Live code | 9 | 5 | Track actual productivity; gross estimated value is NOT net profit |
| C16 | Field Report tab | **Missing — placeholder** | 10 | 5 | Empty UI; needs the actionable report planned in TODO |

## B. Imagery and multi-satellite analysis

| ID | Feature on main | Status | I/10 | F/5 | Practical use / important qualification |
|---|---|---|---:|---:|---|
| C17 | Automated initial historical backfill and ongoing satellite ingestion jobs | Live code | 9 | 4 | Reduce manual downloading and processing; worker must run |
| C18 | Sentinel-2 multispectral indices: NDVI, NDRE, NDMI, GNDVI, EVI2, NDWI, SAVI, MSAVI, BSI, NDTI, CCCI, ReCI, MCARI | Live code | 10 | 4 | See vegetation and canopy variability; some bands are 20 m native resolution |
| C19 | Sentinel-1 RTC VV, VH, VV/VH and dual-pol RVI | Live code | 9 | 4 | Radar signal during cloud cover; **not a crop-health diagnosis** |
| C20 | Ascending/descending relative-orbit separation | Live code | 9 | 5 | Avoid mixing incomparable radar viewing geometry |
| C21 | Landsat surface-temperature (LST) imagery | Live code | 7 | 3 | Observe thermal spatial patterns; not leaf temperature or root-zone moisture |
| C22 | Private Cloud Optimized GeoTIFFs and TiTiler map tiles | Live code | 9 | 4 | Render actual geospatial rasters over field maps |
| C23 | Per-scene clouds, quality masks, valid-pixel percentages and usable/skipped status | Live code | 10 | 5 | Avoid using unreliable optical observations as crop facts |
| C24 | Cross-satellite timeline with radar fallback when optical scenes are cloudy | Live code | 10 | 4 | Find the best available observation for a date |
| C25 | Index maps and field-level median/mean statistics | Live code | 9 | 4 | Locate stronger/weaker relative areas |
| C26 | Optical index time series, radar trend plots and farm activity markers | Live code | 9 | 4 | Follow change across the crop season |
| C27 | General previous/crop-start/7/14/30-day/custom metric comparison | Live code | 9 | 4 | Answer what changed and when |
| C28 | Pixel-by-pixel satellite change rasters | Live code | 9 | 4 | Spatially locate changed areas; must compare appropriate sensors/resolutions |
| C29 | Field-relative index anomaly polygons, severity and affected acreage | Foundation | 9 | 3 | Prioritize scouting; anomalous relative to field, NOT proven disease/stress |
| C30 | Pairwise persistent/new/resolved anomaly overlap areas and geometry | Foundation | 9 | 3 | Understand how mapped anomalies move across dates; not yet full-season tracking |
| C31 | Metric-specific radar chart labels and neutral radar interpretation | Live code | 8 | 4 | Avoid treating higher RVI or backscatter as automatically healthy |
| C32 | Modelled historical weather and 6-day forecast via Open-Meteo | Live code | 10 | 4 | Rain, temperature, humidity, wind and ET0 context; NOT a field sensor |
| C33 | Provenance labels, historical fallback, bounded cache and weather diagnostics | Live code | 8 | 4 | Distinguish reanalysis / historical forecast / recent model / forecast |
| C34 | Growing degree days from complete daily temperature history | Foundation | 9 | 4 | Heat-accumulation context; incomplete history explicitly unavailable |
| C35 | Radar 3-day rainfall and optical NDVI/NDMI context | Foundation | 8 | 4 | Explain possible contributing conditions without attributing cause |

## C. Engineering and reliability

| ID | Feature on main | Status | I/10 | F/5 | Practical use |
|---|---|---|---:|---:|---|
| C36 | PostgreSQL/PostGIS canonical field and satellite data schema | Live code | 9 | 5 | Support spatial queries, integrity and migrations |
| C37 | Durable per-scene metrics and canonical raster paths | Live code | 8 | 5 | Repeatable retrieval and processing |
| C38 | Worker idempotency, cloud-skip handling, error states and refresh | Live code | 9 | 4 | Keep observing fields without duplicating records |
| C39 | Automated tests, schema drift checks, web build/lint, worker and tiler CI | Live code | 9 | 5 | Reduce deployment regressions |
| C40 | Production weather usage/licensing configuration | Foundation | 8 | 4 | Licensed key needed in commercial production; public service is not a default commercial plan |

## D. Not on main: in-review feature

| ID | Feature | Status | I/10 | F/5 | Important qualification |
|---|---|---|---:|---:|---|
| R01 | Crop- and farmer-confirmed stage-aware radar variation screening with same-orbit prior passes, VH/VV/RVI thresholds and weather/optical context | **Open PR #10**, not merged | 8 | 3 | Conservative, exploratory field-median screening; currently often returns insufficient evidence with only 5–7 passes per orbit. Not validated diagnosis or automatic alert |

PR: https://github.com/abhijatain/farm-platform/pull/10

## Critical distinctions for product copy

1. Field-relative NDVI/NDMI anomalies are NOT named crop diseases.
2. Sentinel-1 radar metrics measure scattering; even strong change does not by itself identify stress or irrigation need.
3. ET0 is **reference** evapotranspiration, not measured actual crop ET or soil water.
4. Sentinel-2 does not support individual rice plant counts, individual weed identification, or small-object diagnosis at native spatial resolution.
5. A stored harvest outcome is not a trained or calibrated **yield prediction**.
6. A stage calendar is not a verified field stage or internationally aligned BBCH assessment.
7. A weather forecast is not observed rainfall; gridded weather is not an installed farm station.
8. The Report tab is empty on main, despite having enough separate data modules to start a useful report.

See the prioritized engineering list in [TODO.md](../TODO.md).

## E. Planned primary interaction channel (NOT built)

| ID | Feature | Status | I/10 | F/5 | Farmer benefit / gap |
|---|---|---|---:|---:|---|
| M01 | WhatsApp field registration, multilingual assistance, farm data collection and reporting | **Not implemented** | 10 | 4 | Farmers can use existing backend through chat without learning the web UI; requires Meta Cloud API, onboarding and privacy/security |
| M02 | Punjabi/Hindi/English simplified reports, SMS-like numbered menus and regional voice notes | **Not implemented** | 10 | 3 | Accessible local-language interactions; script and speech recognition accuracy need field testing |
| M03 | WhatsApp opt-in updates, image reports and human support | **Not implemented** | 10 | 4 | User-controlled proactive weather/satellite updates, readable reports and genuine staff handoff |

These are core product priorities, not an already deployed chatbot. Full requirements, architecture and rollout are in [WhatsApp-first plan](WHATSAPP_FIRST_PRODUCT.md) and TODO tasks T61–T80. The assumption that ~80% of farmers will use WhatsApp is a **hypothesis for pilot measurement**, not a verified market share.
