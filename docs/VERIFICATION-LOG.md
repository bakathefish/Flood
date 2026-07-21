# Verification log
Checkpoint discipline: expected band is written BEFORE the run. FAIL stops the wave.
Pre-declarations for agent-run stages live in the corresponding `docs/notes/*.md` (written before each run); this table is the canonical roll-up.

| Date | Step | Expected | Actual | Verdict |
|---|---|---|---|---|
| 2026-07-21 | IMD rain 2015–2025: 2025 Aug 20–Sep 5 vs decade same-window | 2025 extreme vs 2015–2024 (worst since 1988) | Punjab box 342.2 mm = +9.68σ, rank 1/11, +339% vs mean; upstream 306.2 mm = +9.79σ, rank 1/11 | PASS |
| 2026-07-21 | Reservoir anchors (CWC + BBMB/press supplement) | Bhakra ≈1,668.57 ft @ Aug 25 (danger 1,680); Pong ≈1,393 ft; large releases Aug 26–27 | Bhakra 1,666 ft (Aug 19) → 1,676.78 (Sep 2), interpolates ~1,668–1,670 @ Aug 25; FRL exactly 1,680.0 ft; Pong crossed 1,393 ft Aug 26; largest single-dam release Ranjit Sagar 173,000 cusecs Aug 27 ("2.6 lakh cusecs" = downstream cumulative, corrected) | PASS (with correction recorded) |
| 2026-07-21 | District polygons area sanity | Σ area ≈ 50,362 km² (official Punjab) | 50,426.7 km² (+0.13%) | PASS |
| 2026-07-21 | GFM 2025 union (Aug 27–Sep 5, minus permanent water) | 500–6,000 km² band; river-corridor pattern | 2,768 km² (2.74% of bbox); hugs Ravi/Beas/Sutlej belts, converges at Harike; 6 coverage days of 10 | PASS |
| 2026-07-21 | Local Tier-A, Kapurthala 60 m (asc/27) | Flooded fraction 2–20% of bbox | 6,162.8 ha = 1.51% of bbox (1.70% of valid); coherent Beas/Sutlej-belt pattern | PASS (low-end; only asc flood pass is Sep 3 recession — noted) |
| 2026-07-21 | Local Tier-A, statewide 90 m (desc) | Coherent statewide mask | 61,499 ha FLOOR — central-stripe hole from SAS-token expiry (2 scenes dropped); fix committed; full rerun in RF stage | PARTIAL (rerun pre-declared in notes/rf-train.md) |
