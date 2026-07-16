# Project Context: AI-Powered Compound Risk Detection Engine — Coke Oven Battery

**Event:** ET AI Hackathon 2026
**Scope decision:** Narrowed from a full multi-department steel plant safety platform down to two core deliverables: (1) a Compound Risk Detection Engine, and (2) a 3D interactive Geospatial Safety Heatmap. Everything else (RAG incident-pattern agent, permit-conflict agent, emergency response orchestrator, compliance audit agent) is roadmap-only — described in slides, not built.

---

## 1. Problem Framing (fact-checked — use these facts only)

**Real incident anchor:** Visakhapatnam Steel Plant (RINL), Andhra Pradesh.
- Date: **June 8, 2025** (NOT January 2025 — this was an earlier draft error, corrected)
- What happened: A ladle carrying molten steel (~1,500°C) exploded due to **entrapped gases in the liquid steel** during rotation/positioning for casting, in the **Steel Melting Shop (SMS)** — NOT the coke oven battery.
- Casualties: 8 dead, 6 injured (2 critical)
- Investigating authority: **Chief Inspector of Factories, Andhra Pradesh** (this falls under the **Factories Act, 1948** — NOT DGMS, since DGMS covers mines only, not steel plants). Any deck reference to "DGMS reports" for this incident should be corrected to "Chief Inspector of Factories" / Factories Act.
- A 3-member external expert committee (headed by Bokaro Steel Plant's director-in-charge) was appointed to investigate.
- Source: The Wire, "Entrapped Gases and Sudden Explosion: Here's How Eight Workers Died in Visakhapatnam Steel Plant."

**Why the coke oven battery is still the right thing to model even though the real incident was in SMS:** the *mechanism* (undetected gas accumulation + no unified intelligence layer connecting sensor readings to operational decisions) generalizes across units. The coke oven battery is chosen as the demo scope because it has richer public process data (see Section 2) and is a well-documented confined-space/toxic-gas hazard zone under OISD-STD-105 permit logic.

**Framing line for the deck:** "Data existed, but no intelligence layer connected it to operational decisions in time — a pattern that repeats across Indian heavy industry, from the Vizag SMS explosion to comparable coke-oven and confined-space incidents nationally."

---

## 2. Real Plant Data (RINL Vizag Steel — use the NEWER figures only)

Two versions of RINL's public infrastructure page exist; they conflict. Use the **newer/current one** (confirmed current by the commissioning-dates table showing Battery 5 built in 2020):

- **5 batteries, 67 ovens each** (335 ovens total) — do NOT use the older "3 batteries" figure
- Oven volumetric capacity: **41.6 m³**
- Dry coal charge per oven: **32 tons**
- Carbonization temperature: **1000–1050°C**
- Coking cycle: **16–19 hours**
- Raw coke oven gas cooling curve: **800°C → 80°C** via direct contact ammonia liquor spray, drawn off by exhauster
- Battery commissioning dates: B1 – 06.09.1989, B2 – 31.10.1991, B3 – 30.07.1992, B4 – 12.04.2009, B5 – 22.12.2020
- Total production capacity (5 batteries): 2.748 Mt BF coke/annum
- Salient features: 7m tall ovens, 100% dry quenching via nitrogen gas, waste-heat power generation at BPTS (Back Pressure Turbine Station)
- Byproducts recovered from crude coke oven gas: ammonia (NH₃), tar, benzol, ammonium sulphate — via the Coal Chemical Plant
- Source: vizagsteel.com/code/Infrastr/ccp.asp and /infrastructure.asp

**Gas hazard thresholds (used as alert logic, cited as international/OISD reference — not claimed as exact Indian statutory ppm values, since a precise Factories Act ppm table wasn't verifiable):**
- CO: alert above 50 ppm (8-hr PEL reference)
- Combustible gas / LEL, per **OISD-STD-105** (Work Permit System — technically an oil & gas industry standard under the Oil Industry Safety Directorate, but its permit-and-gas-test format is the de facto template adapted across Indian process industries including steel):
  - No hot work permitted unless LEL reading is **zero**
  - Confined space entry allowed up to **5% LEL** without breathing apparatus
  - Entry with air-supplied mask allowed up to **20% LEL**
  - Minimum oxygen level: **19% vol**

---

## 3. Core Risk Rule (one-sentence definition — do not let logic drift from this)

> Compound risk is flagged on an oven when: **gas concentration exceeds the safe threshold** (CO > 50 ppm OR %LEL > 5%) **AND** an **active hot-work or confined-space permit** exists on/near that oven **AND** a **maintenance or exhauster-fault flag** is active — the three-factor combination that no single sensor, viewed alone, would catch.

This is the differentiator: individually-monitored sensors miss the compound pattern; the engine's job is to correlate across streams.

---

## 4. Data Schemas (build these exactly — four tables)

### 4.1 Oven Registry (static)
| field | type | notes |
|---|---|---|
| oven_id | string | e.g. `B1-O01` through `B1-O67` — model ONE battery (67 ovens) for the demo |
| battery_id | string | `B1` |
| volume_m3 | float | 41.6 (constant) |
| coal_charge_tons | float | 32 (constant) |

### 4.2 Sensor Readings (time-series — the main simulated stream)
| field | type | notes |
|---|---|---|
| timestamp | datetime | simulate a 48–72 hr rolling window |
| oven_id | string | FK to registry |
| gas_temp_c | float | follow real decay curve 800°C→80°C during draw-off, with noise; NOT flat random |
| co_ppm | float | baseline low, spikes in injected risk windows |
| combustible_gas_pct_lel | float | baseline low, spikes in injected risk windows |
| exhauster_status | enum | `normal` / `fault` |
| maintenance_flag | bool | rare during normal ops |

### 4.3 Permit Log
| field | type | notes |
|---|---|---|
| permit_id | string | unique |
| oven_id | string | FK — or `zone_id` if permit covers multiple ovens |
| permit_type | enum | `hot_work` / `confined_space_entry` / `cold_work` |
| status | enum | `active` / `closed` |
| issued_time | datetime | |
| valid_until | datetime | |

### 4.4 Zone/Layout (static — feeds the 3D heatmap)
| field | type | notes |
|---|---|---|
| zone_id | string | e.g. per battery or per group of ~10 ovens |
| x, y, z | float | 3D coordinates for layout placement |
| zone_type | enum | `oven_battery` / `coal_chemical_plant` / `exhauster_house` |

### 4.5 Risk Engine Output (computed, not raw data)
| field | type | notes |
|---|---|---|
| oven_id | string | |
| timestamp | datetime | |
| risk_score | float | 0–1, or categorical low/medium/high |
| risk_reason | string | plain-language explanation, e.g. "CO 78ppm + active hot-work permit + exhauster fault" |

---

## 5. Build Phases (in order)

1. **Synthetic data generator** — Python. Normal operation with realistic noise around real baselines above; inject 5–8 deliberate overlapping risk windows (gas spike + open permit + maintenance flag, same oven, same time) as ground truth. Output: sensor CSV, permit CSV.
2. **Detection engine** — rule-based implementation of the Section 3 risk rule first (explainable, defensible). Optional stretch: a simple ML layer (gradient boosting / logistic regression) trained on the synthetic data for a continuous risk_score, framed as an enhancement over the rule engine, not a replacement.
3. **Evaluation** — confirm the engine catches all injected risk windows and stays quiet during normal periods (report a simple precision/recall-style summary, even on synthetic data).
4. **3D Geospatial Heatmap** — see Section 6 below for full spec.
5. **Dashboard assembly** — combine risk engine output + 3D heatmap + a plain-language "why flagged" panel + a time-scrubber/playback control to demo the 48–72 hr window live.
6. **Roadmap slides** — RAG incident-pattern agent, permit-conflict agent, emergency response orchestrator, compliance audit agent: presented as designed-not-built, one slide each.
7. **Fact-check pass on the deck** — apply Section 1 and Section 2 corrections before final submission.

---

## 6. 3D Interactive Geospatial Heatmap — Spec for Claude Code

**Goal:** A 3D, scrollable/interactive plant layout (NOT a flat 2D map) showing 67 ovens across one battery, color-coded live by risk_score from the detection engine, with the ability to rotate/pan/zoom and click into individual ovens for detail.

**Suggested stack:** React + Three.js (via `react-three-fiber` and `drei` for camera controls) for the 3D scene; this fits well as a web dashboard artifact. If building outside Claude.ai artifacts (i.e., in Claude Code as a standalone app), the same stack applies, or a plain Three.js scene embedded in a lightweight web app (e.g., Vite + vanilla Three.js) if avoiding React overhead.

**Scene requirements:**
- Represent one coke oven battery as a **row/grid of 67 rectangular oven blocks** (schematic — not a literal architectural model; a stylized elongated battery structure with individual oven chambers is sufficient and expected at hackathon stage)
- Each oven block colored by current `risk_score`: green (low) → yellow (medium) → red (high), updating as the simulated timeline advances
- **Camera controls:** orbit (rotate), pan, zoom — via `OrbitControls` from drei/three — so the user can scroll/drag to inspect the battery from any angle
- **Click interaction:** clicking an oven block opens a detail panel showing that oven's current `co_ppm`, `combustible_gas_pct_lel`, `gas_temp_c`, `exhauster_status`, `maintenance_flag`, active permits, and `risk_reason` if flagged
- **Time control:** a scrubber/play button along the bottom that advances the simulated 48–72 hr window, with oven colors updating live as it plays — this is the "wow" moment for the demo
- **Zone grouping (optional but recommended):** cluster ovens into visual sub-groups (e.g., every ~10 ovens) matching the `zone_id` in the layout schema, so the heatmap can also show zone-level aggregate risk when zoomed out, and individual oven detail when zoomed in
- **No individual worker GPS tracking.** If an occupancy layer is added, it must be zone-level only (worker present in zone: yes/no), framed as consistent with RFID/UWB-based personnel tracking already mandated by DGMS in underground coal mining — NOT continuous per-person location tracking. This is an ethical boundary, not just a technical simplification: individual real-time worker surveillance was intentionally scoped out.

**Data flow into the 3D scene:**
- The scene reads from the Risk Engine Output table (Section 4.5) and Zone/Layout table (Section 4.4)
- Poll or stream risk_score updates per oven_id per timestamp as the time-scrubber advances
- Clicking an oven looks up its full sensor/permit context from tables 4.2 and 4.3 for that timestamp

**Design tone:** industrial/technical, not playful — dark background, amber/red/green risk indicators, clean sans-serif labels (oven IDs, ppm values). This should read as a credible safety-operations tool, not a game.

---

## 7. What NOT to build (explicitly out of scope for this hackathon)

- Real-time SCADA or live sensor integration — no such access exists; all data is clearly-labeled synthetic
- Individual worker GPS/location tracking — zone-level occupancy only, if included at all
- Full RAG pipeline over DGMS/OISD documents — roadmap slide only
- Autonomous emergency response actions — roadmap slide only
- Modeling all 5 batteries / 335 ovens — one battery (67 ovens) is the demo scope; note the rest as "same architecture, not instantiated in this demo" in the limitations slide

---

## 8. Deck Fact-Check Checklist (apply before final submission)

- [ ] Incident date corrected to June 8, 2025
- [ ] Incident mechanism corrected to ladle/entrapped-gas explosion in SMS, not coke oven battery gas explosion
- [ ] "DGMS" replaced with "Chief Inspector of Factories / Factories Act, 1948" for the Vizag incident specifically
- [ ] Plant figures use the 5-battery / 41.6 m³ / 32-ton / current source only (not the older 3-battery page)
- [ ] OISD-STD-105 cited accurately as an oil & gas industry standard adapted for permit-logic purposes, not a steel-specific regulation
- [ ] Gas thresholds (CO 50ppm, LEL tiers) labeled as reference values, not claimed as exact Indian statutory limits
- [ ] Limitations slide clearly states all sensor/permit/worker data is synthetic, and states what was scoped out and why
