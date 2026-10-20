# Dashboard Design Document
**Project:** AI-Based Aquatic Habitat Suitability Assessment & Water Body Restoration Decision Support System
**Derived from:** SRS v1.0 (Mehar Bajaj, 24BAI1120, VIT Chennai)
**Scope:** Web dashboard only (HTML/CSS/JavaScript client, per Section 3.4 of the SRS)

---

## 1. Design Goals (from SRS)

The dashboard has to satisfy a few hard constraints before it satisfies anything aesthetic:

| Constraint | Source | Design consequence |
|---|---|---|
| First-time evaluator finds the Habitat Suitability Score (HSS) and one recommendation within 30 seconds, no training | REQ 5.4 Usability | HSS and top recommendation must be above the fold on the landing view |
| Every screen shows last-updated timestamp | Section 3.1 | Persistent timestamp in the header, not buried per-widget |
| Stale/offline data shown as an explicit state, never a silently frozen last value | REQ-MON-5 | Dedicated "stale" visual state on every live widget |
| HSS is an AI-generated estimate, not fact | REQ-PRED-5 | Permanent, visible disclosure badge next to the score |
| No score if inputs are missing/invalid | REQ-PRED-6 | Score widget has an explicit "unavailable" state, not a 0 or blank |
| Species results are suitability estimates, not presence predictions | REQ-SPEC-3 | Caption under species panel, always visible |
| Simulated score never overwrites live data | REQ-SIM-2/3 | Simulator always shows *live* and *simulated* side by side, visually distinct |
| Auth required; single role, no admin panel | Section 2.3, 5.3 | One login screen, one dashboard shell, no role switcher |
| English only, desktop + mobile browser, no native app | Section 2.5, 6 | Responsive single web app, no platform-specific UI |

Everything below is built around these, not around decoration.

---

## 2. Information Architecture

Five logical screens, one persistent shell:

```
Login
  └── Dashboard Shell (header + left nav, persists across all screens below)
        ├── 1. Live Monitoring        (default landing screen after login)
        ├── 2. Restoration Recommendations
        ├── 3. Intervention Simulator
        └── 4. Historical Trends
```

There is no separate "species" screen — species suitability is a panel inside Live Monitoring, since it's derived from the same reading and the evaluator needs it in the same glance as the HSS (Usability requirement).

---

## 3. Global Shell

```
┌─────────────────────────────────────────────────────────────────┐
│ 🌊 Aquatic Habitat DSS         Device: NODE-01   ⏱ Updated 2m ago│
├───────────┬───────────────────────────────────────────────────--┤
│ Live       │                                                     │
│ Monitoring │              [ active screen content ]              │
│ Restoration│                                                     │
│ Simulator  │                                                     │
│ History    │                                                     │
│            │                                                     │
│ ⎋ Log out  │                                                     │
└───────────┴─────────────────────────────────────────────────────┘
```

- **Header, always visible:** app name, connected device ID, and a live-updating "last updated" timestamp with a colored dot (green = fresh, amber = approaching stale, red = stale/offline per REQ-MON-5). This single element satisfies the "every screen shows last-updated timestamp" requirement without repeating it per-widget.
- **Left nav (collapses to a bottom tab bar on mobile):** four items exactly matching the four screens. No nested menus — the user set is one role, so there's nothing to hide behind permissions.
- **Global offline banner:** if the device is stale/offline, a thin red banner appears under the header on *every* screen ("No data from NODE-01 for 34 min — showing last known readings"), so the user never mistakes old numbers for current ones no matter which screen they're on.

---

## 4. Screen 1 — Login

Single-purpose, minimal:

```
┌───────────────────────────────┐
│        🌊  Aquatic Habitat DSS │
│                                │
│   Username  [______________]  │
│   Password  [______________]  │
│                                │
│          [   Log in   ]       │
│                                │
│   Error text appears here     │
│   if credentials are wrong    │
└───────────────────────────────┘
```

- No self-registration link (SRS explicitly excludes it).
- No "forgot password" flow required by SRS — if included at all, keep it a stretch/optional element, not a blocker.
- Failed auth shows inline error text, not a browser alert.

---

## 5. Screen 2 — Live Monitoring (the landing screen)

This is the screen the 30-second usability requirement is graded on, so priority order top-to-bottom is deliberate: **score → species → raw sensors**, not the reverse.

```
┌─────────────────────────────────────────────────────────────────┐
│  HABITAT SUITABILITY SCORE                    ⓘ AI estimate      │
│                                                                   │
│           ┌───────────┐                                          │
│           │    72     │      GOOD                                │
│           │  /100     │      (60–79)                             │
│           └───────────┘                                          │
│           gauge/arc fill, color-coded by band                    │
├─────────────────────────────────────────────────────────────────┤
│  INDICATOR SPECIES SUITABILITY                                   │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                 │
│  │ Tilapia    │  │ Common Carp│  │ Gastropods │                 │
│  │  ● High    │  │  ● Moderate│  │  ● High    │                 │
│  └────────────┘  └────────────┘  └────────────┘                 │
│  Estimates of habitat suitability, not predictions of            │
│  actual species presence. Source: FAO / literature tolerance     │
│  ranges (ⓘ per-card, expandable).                                │
├─────────────────────────────────────────────────────────────────┤
│  CURRENT READINGS                                                │
│  pH 7.1   Temp 26.4°C   Turbidity 12 NTU   TDS 340 mg/L  DO 6.2  │
│  each with a small sparkline (last few hours) and in/out-of-     │
│  range color coding                                              │
└─────────────────────────────────────────────────────────────────┘
```

Design rules for this screen:

- **HSS gauge:** a semicircular or radial gauge (not a bare number) so "Good" registers visually before the user reads the digits. Four color bands map directly to REQ-PRED-2's categories: Poor (red, 0–39), Moderate (amber, 40–59), Good (light green, 60–79), Excellent (deep green, 80–100).
- **"ⓘ AI estimate" badge** sits permanently next to the score, not in a tooltip that requires hovering — REQ-PRED-5 asks for clear indication, so it should be readable without interaction, with the tooltip only adding detail on click/tap.
- **Unavailable state:** if inputs are missing (REQ-PRED-6), the gauge is replaced by a neutral placeholder: "Score unavailable — missing [pH, DO]" rather than showing 0 or a stale number.
- **Species cards:** three dot-colored states only (High/Moderate/Low green-amber-red), consistent with the HSS palette so the user learns one color language for the whole app.
- **Sensor row:** compact, five equal-width tiles, each with value + unit + tiny 1–2hr sparkline + a colored left border if the value is outside the healthy range (this is what feeds the Recommendations screen, so showing it here creates a visual link between "this number is red" and "here's a recommendation about it").
- **Stale indicator (REQ-MON-5):** if triggered, the whole "Current Readings" block dims slightly and each tile gets a small clock icon with "last seen HH:MM" instead of a live-looking number.

---

## 6. Screen 3 — Restoration Recommendations

```
┌─────────────────────────────────────────────────────────────────┐
│  DETECTED ISSUES & RECOMMENDATIONS                               │
│                                                                   │
│  ⚠ Dissolved Oxygen low (4.1 mg/L, healthy range 5–8 mg/L)       │
│     → Install a floating aerator near the inflow point.          │
│     → Reduce organic runoff from the upstream bank.              │
│                                                                   │
│  ⚠ Turbidity high (48 NTU, healthy range < 25 NTU)               │
│     → Add a vegetative buffer strip to reduce sediment inflow.   │
│                                                                   │
│  (if nothing is out of range)                                    │
│  ✓ All monitored parameters are within healthy ranges.           │
│    No restoration action currently required.                     │
└─────────────────────────────────────────────────────────────────┘
```

- One card per flagged parameter, not one giant paragraph — each card names the *cause* (parameter + measured value + healthy range) before the *action*, so the evaluator can audit the logic (this is a rule-based engine, and the UI should make the rule visible, reinforcing "truth over hype" rather than a black-box feel).
- REQ-REC-3's "nothing required" state is a first-class empty state (green check, calm tone), not just an empty list — an empty list reads as broken, a check mark reads as good news.
- No buttons to "dispatch" or "trigger" anything — REQ-REC-4 makes these advisory-only, so the UI must not even imply an action can be automated from here.

---

## 7. Screen 4 — Intervention Simulator

This screen has one job: make it obvious that the simulated number is *not* the live number.

```
┌─────────────────────────────────────────────────────────────────┐
│  WHAT-IF SIMULATOR                                                │
│                                                                   │
│  Parameter:  [ Dissolved Oxygen ▾ ]                              │
│  Value:      4.1  ────────●─────────────  12.0   (mg/L)         │
│                                                                   │
│  ┌───────────────────┐        ┌───────────────────┐             │
│  │  LIVE SCORE        │        │  SIMULATED SCORE   │             │
│  │      58             │  →     │      74            │             │
│  │    Moderate          │        │      Good            │             │
│  └───────────────────┘        └───────────────────┘             │
│                                                                   │
│  Simulated values are not saved and do not affect stored          │
│  sensor data.                                                     │
└─────────────────────────────────────────────────────────────────┘
```

- **One dropdown, one slider** — REQ-SIM-1/5 restrict this to a single parameter at a time, so there is deliberately no multi-parameter form; the UI shouldn't offer a capability the backend doesn't support.
- Slider is bounded to physically valid ranges (REQ-SIM-4) — e.g., pH slider can't go outside 0–14 — with the bound values labeled at each end of the track.
- **Live vs. Simulated is always a two-card side-by-side layout**, never a single card that swaps its value on drag — this is the main defense against a user mistaking a simulated score for reality (REQ-SIM-2/3).
- A subtle visual treatment (e.g., dashed border, or slightly muted color) on the "Simulated" card versus a solid border on "Live" reinforces which one is real.

---

## 8. Screen 5 — Historical Trends

```
┌─────────────────────────────────────────────────────────────────┐
│  HISTORICAL TRENDS                                               │
│                                                                   │
│  Parameter: [ Habitat Suitability Score ▾ ]  Range: [ 7 days ▾ ] │
│                                                                   │
│    100 ┤                                                          │
│     80 ┤        ╭──╮                                              │
│     60 ┤────╮───╯  ╰───╮──────                                    │
│     40 ┤    ╰──╯       ╰──╮                                       │
│      0 ┼───────────────────────────────────────                  │
│        Mon  Tue  Wed  Thu  Fri  Sat  Sun                          │
│                                                                   │
│  (or, if insufficient data:)                                      │
│  Not enough historical data for the selected range yet.           │
│  Try a shorter range or check back after more readings arrive.    │
└─────────────────────────────────────────────────────────────────┘
```

- Two controls only: parameter selector (any of the five sensors, or HSS itself) and a time-range selector — matches REQ-HIST-1/2 without over-building a full BI-style filter panel that this project doesn't need.
- The color bands from the HSS gauge (red/amber/light-green/deep-green) reappear here as horizontal reference bands behind the HSS line chart, so a dip below "Good" is visible at a glance rather than requiring the user to read axis numbers.
- The "insufficient data" message (REQ-HIST-3) replaces the chart area entirely rather than showing an empty/broken-looking chart frame.
- Load target is 5 seconds (REQ-HIST-4) — design-wise this means: fetch on selector change with a lightweight inline spinner over the chart area, not a full-page loading state.

---

## 9. Shared States (apply across every screen)

| State | Visual treatment |
|---|---|
| Loading | Skeleton blocks or a small inline spinner in the affected widget only — never a full-page blocker |
| No data / error | A calm, explicit message inside the widget's own boundary ("No data received yet") — per SRS, never a blank chart |
| Stale/offline | Amber → red timestamp dot in header, red banner, dimmed live widgets with "last seen" timestamps |
| AI-estimate disclosure | Persistent small badge, not just a tooltip |
| Advisory-only actions | No buttons that imply automatic control anywhere in the app |

---

## 10. Visual Language

- **Palette:** a calm blue/teal base (water, not corporate-tech), with the four suitability colors (red/amber/light-green/deep-green) reserved *exclusively* for score/status meaning — they should never be used decoratively elsewhere, so their meaning stays unambiguous.
- **Typography:** one legible sans-serif, large numerals for the HSS (this is the number the 30-second test hinges on), smaller regular weight for supporting labels and captions.
- **Density:** generous whitespace over dense tables — the target user is a researcher/evaluator, not a power user monitoring dozens of nodes, so this is a single-node, single-glance dashboard, not an ops console.
- **Icons:** minimal — a droplet/wave mark for branding, dot indicators for status, a clock for staleness, an info circle for disclosures. No decorative illustration that competes with the data.

---

## 11. Responsive Behavior

- **Desktop (≥ 1024px):** left nav as a fixed sidebar; Live Monitoring uses the 3-row layout in Section 5 at full width; species cards in a row of three.
- **Tablet (600–1023px):** sidebar collapses to icons-only; species cards wrap to 2+1; sensor tiles wrap to a 3+2 grid.
- **Mobile (< 600px):** nav becomes a bottom tab bar (4 icons); every panel stacks to full-width single column; the HSS gauge shrinks but stays the first thing visible on load; Simulator's live/simulated cards stack vertically instead of side-by-side, but keep the visual distinction (dashed vs. solid border) so the "which one is real" cue survives the stack.

---

## 12. Traceability Note

Every screen above maps 1:1 to the "logical screens" listed in SRS Section 3.1 (User Interfaces) and pulls its states directly from the functional requirements in Section 4 (REQ-MON, REQ-PRED, REQ-SPEC, REQ-REC, REQ-SIM, REQ-HIST). Detailed component specs (exact pixel spacing, component library choice, exact hex values) are intentionally left to the implementation phase — this document fixes *what appears where and why*, consistent with the SRS's own note that "detailed screen layouts... will be captured in a separate low-fidelity wireframe set during design."
