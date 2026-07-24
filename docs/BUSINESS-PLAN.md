# Sailaab: Business Plan (optional festival deliverable)

**Posture:** Sailaab's core is a public good: MIT code, CC-BY data, zero-cost
to run, free forever (a festival rule and a design principle). This plan is a
*sustainability and deployment* plan: how the system reaches the institutions
that should run on it, and what funds the scale-out. It is reviewed separately
from the synopsis (ISB mentorship track); nothing here changes the open core.

## 1. Product

A five-module open pipeline (2025 flood atlas, decade hazard atlas, impact
engine (₹351–523 cr damage band), district forecaster (~10-day demonstrated
lead), live 6-hourly monitor with ਪੰਜਾਬੀ/हिन्दी/EN alerts) running today on
free public infrastructure with zero accounts. 386 automated tests; validated
against Copernicus GFM, Sentinel-2, ISRO NDEM, and the government's own
girdawari (ρ = 0.72).

## 2. The problem, priced

- The 2025 Punjab flood: ₹14,000 crore interim state loss estimate; ₹1,600
  crore central assistance; ₹71 crore immediate state relief (official figures,
  `data/official_relief_2025.csv`).
- Punjab has **zero CWC flood-forecast stations** (absent from CWC's own
  state-wise table; corroborated current), so there is no incumbent public
  district-forecast layer to displace.
- Girdawari damage assessment deployed **2,167 patwaris** for weeks; the
  satellite layer that could target it ran for ~₹0.
- PMFBY insurers and lenders lack an independent, reproducible loss extent.

## 3. Value proposition and the AI component

For a district collector: which tehsils flood repeatedly (named list), what is
flooding *now* (6-hourly), what is likely *next window* (live forecaster,
activates in its trained domain), and what the damage is worth (₹ band, DES
yields). The AI is the pipeline: an RF SAR classifier, a self-labeled decade of
training data, an XGBoost forecaster that is ablation-stress-tested and honest
about persistence. The discipline is the differentiator institutions can
audit.

## 4. Sustainability model (three tiers)

| Tier | Who pays | What they get | Status |
|---|---|---|---|
| **Open core** | nobody, free forever | everything public today | live |
| **Institutional instances** | state SDMAs / Revenue Depts (procurement or MoU) | hosted multi-state instance, SLAs, girdawari-verification exports per village-circle, training | pilot-ready |
| **Analytics services** | PMFBY insurers, lenders, CSR/climate funds | independent loss-extent audits, recurrence underwriting layers | roadmap |

Reference pricing (assumption, to be tested in mentorship): a per-state
instance priced against the avoided cost of manual survey targeting; even 5%
efficiency on one girdawari cycle dwarfs any realistic hosting fee. Core infra
cost today: ₹0/month (GitHub CI + open data). Scale compute: IndiaAI Compute
subsidy lane (student/institution route documented in-repo).

## 5. Roll-out

- **Phase 0 (done):** Punjab system live through monsoon 2026; jurors can watch
  CI commit.
- **Phase 1 (this monsoon):** PSDMA + worst-hit District Collectors outreach
  (drafted, dispatches with this submission); operational feedback loop;
  Bhoonidhi/EOS-04 Indian-SAR cross-validation.
- **Phase 2 (next two quarters):** three-state expansion (the pipeline is a
  bounding box + district file; Assam and Bihar have NRSC frequency atlases but
  no live open district layer), Bhashini voice alerts, village-circle girdawari
  integration.
- **Phase 3:** national coverage via IndiaAI/NRSC partnerships; formal
  engagement with CWC on the station-gap finding.

## 6. Marketing and distribution

The alerts are the distribution: vernacular, free, and quotable. District flood
briefs (20 ship in-repo) are the door-opener artifact for collectors. The
dam-headroom and station-gap findings are press-grade stories that carry the
system's name into policy rooms (SANDRP already covers this space).

## 7. Risks

- **Data feeds go dark**: happened (BBMB → CWC, Jul 2025). Mitigated and
  *proven survivable by ablation*: detection skill does not depend on the feed.
- **Single-sensor reliance**: EOS-04/Bhoonidhi second SAR source in Phase 1.
- **Adoption friction**: zero-login open core removes procurement as a
  precondition; institutions can adopt before they contract.
- **Founder concentration**: solo student builder; mitigations: 459 tests,
  full method paper, verification log. The system is transferable by design.
  ISB mentorship asks: government procurement navigation, PPP structuring.

## 8. Team

Solo student builder (Punjab), built during the 2026 monsoon. The repo is the
CV: github.com/bakathefish/Flood · live: bakathefish.github.io/Flood
