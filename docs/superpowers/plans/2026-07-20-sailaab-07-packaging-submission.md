# Sailaab 07 — Packaging & Submission (Waves 6+7) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax. This plan is checklist-verified (content deliverables, not unit-testable); every task has explicit acceptance criteria. Video/portal tasks are user-driven; agents prepare assets and drafts.

**Goal:** GEE App, complete repo docs, landing page, synopsis PDF, ≤2-min video, and the submitted festival entry (Jul 25), built from Waves 1–5 outputs.

**Architecture:** All numbers flowing into synopsis/video come from `docs/VERIFICATION-LOG.md` and `atlas/` outputs — no number appears in a public artifact unless it has a log row or an atlas file behind it (the anti-hallucination gate for our own claims).

**Tech Stack:** GEE Apps, GitHub Pages, OBS + CapCut/DaVinci, any PDF-capable editor.

---

### Task 1: GEE App

- [ ] **Step 1:** In the Code Editor, build `gee/04_app.js`: `ui.Map` with layers — 2025 RF flood (+Tier-A-agreement confidence), decade frequency raster (import the exported asset), crop-damage choropleth (styled districts from the stats CSV re-uploaded as an asset or FeatureCollection), permanent water. Split-panel (`ui.SplitPanel`) pre/post VV swipe. District click → `ui.Panel` with flooded km², crop ha, population exposed. About panel: one-paragraph method + repo link + data credits.
- [ ] **Step 2:** Publish (Apps → New App). **Acceptance:** loads logged-out in an incognito window; all layers render; district click works; swipe works.
- [ ] **Step 3:** Commit `gee/04_app.js` + app URL in README — `git commit -m "feat: public GEE app"`

### Task 2: Repo docs finalization

- [ ] **Step 1:** README.md final: name + one-line pitch, hero image (atlas overview map), app link, live-monitor badge/status, architecture diagram (text/mermaid fine), quickstart (pytest, pipeline runs), links to METHOD.md / DATA-SOURCES.md / VERIFICATION-LOG.md, license, "built for India AI Impact Festival 2026" line.
- [ ] **Step 2:** METHOD.md completeness pass — every section 1–6 present; every headline number traceable to a log row; limitations section consolidated (urban under-detection, GAUL vintage, bootstrapped labels, snapshot-vs-season, estimate caveats).
- [ ] **Step 3: Acceptance:** a stranger can answer "what is this, how good is it, how do I run it" from README alone. Commit — `git commit -m "docs: final README and method pass"`

### Task 3: Landing page (GitHub Pages)

- [ ] **Step 1:** `docs/index.html` (Pages from /docs): name, tagline, four cards (2025 Atlas / Decade Hazard / Forecaster / Live Monitor) each with one image + one number, buttons → App, Repo. Reads `monitor/latest.json` client-side for the live strip ("Last pass: … · Flagged: …"). Self-contained CSS, dark/light safe.
- [ ] **Step 2:** Enable Pages; **acceptance:** phone + desktop render, live strip populates. Commit.

### Task 4: Synopsis PDF

- [ ] **Step 1:** Draft per the structure in strategy-doc Wave 6 §4 (problem → gap → system → AI component → data table with gov sources highlighted → results → SDGs 2/11/13 → users → roadmap incl. Bhashini + dam-aware forecasting → open-source note + all links). Use ONLY logged numbers; include: both spatial-CV fold accuracies, GFM/NDEM agreement, crop-loss vs official band, LOYO table summary, hindcast statement verbatim.
- [ ] **Step 2:** Fit to the format captured in `docs/festival-form/` screenshots (page/word limits govern).
- [ ] **Step 3: Acceptance read (user):** every claim checked against VERIFICATION-LOG; no orphan numbers. Export PDF → `docs/festival-form/synopsis.pdf`. Commit.

### Task 5: Video (≤2 min)

- [ ] **Step 1: Assets list** (agents prepare): SAR timelapse GIF (GEE `getVideoThumbURL`, Aug 20→Sep 5 mosaics), app screen-captures (district click, swipe, live monitor with today's date), NDEM-PDF-vs-app side-by-side, causal figure, SHAP figure, frequency map, numbers-string close card ("11 monsoons · 40+ mosaics · 23 districts · 3 languages · validated against 2 space agencies" — adjust to logged reality), Punjabi alert arriving on a phone (screen-record Telegram or the JSON rendered in a phone mock).
- [ ] **Step 2: Script** = strategy-doc Wave 7 v2 beats: personal open (first-person Punjab framing) → gap → system demo → hindcast moment → Punjabi alert → live close. Write VO word-for-word (~260 words max), read at recording pace ≥2× before shooting.
- [ ] **Step 3: Shoot + edit (user):** OBS + phone VO; captions ON (jurors skim muted); 10 s under limit. **Acceptance:** a non-technical viewer can retell the story after one watch; every stat shown matches the synopsis.
- [ ] **Step 4:** Export per portal spec (or YouTube unlisted if the form takes links). Commit script + asset list.

### Task 6: Submission (Jul 24 dry-run, Jul 25 submit)

- [ ] **Step 1 (Jul 24 evening):** Full portal dry-run — every field filled, files uploaded, STOP before final submit. Screenshot the completed form.
- [ ] **Step 2 (Jul 25):** Final proofread → submit → **screenshot the confirmation** → `docs/festival-form/`. Commit — `git commit -m "chore: festival submission archived"`
- [ ] **Step 3:** Post-submit: tag the repo `v1.0-festival`, then hands off to Fallout (due Jul 26).

### Task 7: Outreach (Day 3, runs early — listed here for completeness)

- [ ] **Step 1:** Short email (user's account) with the district atlas PDF to Punjab SDMA, Revenue Dept, and 2–3 worst-hit District Collectors — offering the tool free, one paragraph, no ask beyond "feedback welcome". Log send date; any reply gets quoted (with permission) in the synopsis as "shared with…".
