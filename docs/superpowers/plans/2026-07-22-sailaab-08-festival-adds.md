# Sailaab 08 — festival adds: CWC gap, 70-year context, reservoir ablation

Three self-contained components, executed in parallel with strict file ownership.
Every component: pure logic in `sailaab/`, tests mirrored 1:1 in `tests/`,
deterministic `pipeline/make_*.py` / `run_*.py` driver, dark house palette
(match `pipeline/make_headroom.py` / `duration_2025.py`), pre-declared note in
`docs/notes/` committed BEFORE actuals, verdict row appended to
`docs/VERIFICATION-LOG.md` at integration.

TDD rule (all components): write the failing test first, then the pure helper,
then the driver. No network in any driver — all inputs are committed CSVs.
Drivers must be re-runnable byte-stable (same CSV in → same CSV/PNG out).

## Component A — CWC flood-forecast station gap (owner: agent A)

**Claim to establish (pre-declared in `docs/notes/cwc-gap.md`):** in CWC's own
state-wise station table (data.gov.in, "as on Jan 2018"), Punjab has ZERO flood
forecasting stations (level or inflow) while the national network counts 226.

Files (exclusive ownership):
- `data/cwc_ff_stations_2018.csv` — cleaned 23-row table from the OGD API pull
  (source uuid `0ff82e77-8f0c-479c-823e-246c0b38a2c6`, GODL licence; raw JSON in
  scratchpad `datagovin/`).
- `sailaab/cwc.py` — `load_stations(path) -> DataFrame` (schema-validated),
  `state_totals(df)` (ranked, level+inflow=total consistency),
  `station_count(df, state)` (absent state → 0, the Punjab semantics),
  `national_totals(df)`.
- `tests/test_cwc.py` — schema (columns, 22 states + any total row excluded),
  national totals 226 = 166 level + 60 inflow, Punjab → 0 via absence,
  Haryana → 1, ranking is stable/descending, absent-state semantics.
- `pipeline/make_cwc_gap.py` → `atlas/cwc_station_gap.png` — horizontal bars,
  states ranked by total stations, Punjab pinned at 0 with annotation; caption
  carries the vintage caveat verbatim from the note.
- `docs/notes/cwc-gap.md` — appends ACTUALS + the currency red-team (below) to
  the pre-declared frame.

**Red-team sub-task (mandatory before any claim wording is final):** check
whether Punjab has CWC flood-forecast stations TODAY (ffs.india-water.gov.in
station list, CWC annual reports 2023–25, news). Both outcomes are pre-worded in
the note; the agent selects the one the evidence supports and cites it.

## Component B — Punjab floods in 70-year context (owner: agent B)

Files (exclusive ownership):
- `data/punjab_flood_damage_history.csv` — consolidated milestones from the
  three OGD resources (uuids in `docs/notes/flood-history.md`), one row per
  (year|period, metric, value, unit, source_uuid).
- `sailaab/history.py` — unit normalisation (`lakh_ha`/`Mha`/`ha` → ha,
  `crore_inr` passthrough), milestone assembly, metric-class tagging
  (flooded_area vs crop_damage_area vs lives vs houses — never conflated),
  validation (no negative values, known units only).
- `tests/test_history.py` — unit conversions exact, metric classes disjoint,
  consolidated CSV schema, the 2.79 Mha and 2016–18 anchor values load
  correctly.
- `pipeline/make_flood_history.py` → `atlas/punjab_flood_history.png` — sparse
  milestone timeline (NOT a dense annual line — the record is sparse and the
  figure must look sparse); distinct markers per metric class; 2025 entered as
  TWO points, labelled: 105,183 ha (our SAR single-pass) and 1.985 lakh ha
  (official girdawari, cumulative). Caption: sources + "no continuous public
  annual series exists" caveat.
- `docs/notes/flood-history.md` — actuals appended to the pre-declared frame.

**Red-team sub-task:** the 1953–2010 "max area 2.79 Mha" row — establish which
year it refers to if the resource or literature allows (1988 is the prior
suspect); if undatable, the figure labels it "worst year, 1953–2010 (year not
published)". No invented year.

## Component C — reservoir-feature ablation (owner: agent C)

Hypotheses, variants, bands: `docs/notes/ablation.md` — COMMITTED BEFORE ANY
RUN. The agent implements and runs only after that commit exists (it does).

Files (exclusive ownership):
- `pipeline/run_ablation.py` — imports `build_dataset`, `loyo_oof`,
  `loyo_metrics_table`, `hindcast_2025` from `pipeline.run_forecaster`
  (read-only reuse; MUST NOT overwrite any run_forecaster output:
  `forecaster_dataset.csv`, `forecaster_loyo_metrics.csv`, `models/*`,
  `forecaster_shap.png`). Runs the four pre-declared variants, writes
  `data/forecaster_ablation.csv`.
- `sailaab/ablation.py` — pure helpers: `variant_features(features, variant)`
  (exact drop-lists), `persistence_scores(core)` (antecedent_fraction as the
  score), `ablation_row(...)` (metric assembly incl. flag metrics).
- `tests/test_ablation.py` — variant feature lists exact (16/10/9), persistence
  score is a pure passthrough of antecedent_fraction, output schema, flags
  computed with the same FLAG_TOPN/FLAG_PROB constants as run_forecaster
  (import them, don't re-declare).
- `docs/notes/ablation.md` — ACTUALS + verdict bins appended after the run.

## Integration (owner: integrator)
- Review each component, run the FULL suite (`python -m pytest -q`), commit per
  component in repo style (`feat(cwc-gap): …`, `feat(history): …`,
  `feat(ablation): …` — no trailers), append VERIFICATION-LOG.md rows.
- Then (separately planned): synopsis §1/§7 updates + PDF rebuild, video-script
  line adds, EOS-04 component (blocked on Bhoonidhi registration).
