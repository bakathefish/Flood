# pipeline/build_daily_observability.py
"""Rebuild the daily district table with observability, not assumed dryness.

The existing table encodes one inference, stated plainly in its own builder:

    A monsoon day with no mask file on disk is an observed dry day, not a gap:
    the fetcher probes every day and only writes a full raster when the probe
    is non-empty.

The probe is a request to the flood service over the whole bounding box. When it
comes back with no flood pixels, the builder writes zero flooded hectares for
all twenty districts. But an empty flood mask over ground the satellite never
imaged is byte-identical to an empty flood mask over ground that is genuinely
dry, and Sentinel-1 images a strip roughly 250 km wide on a six-to-twelve day
repeat, not a state every day.

Measured against the acquisition footprint, over the 8,460 district-days from
2022 to 2025: only 16.6% were imaged across at least 95% of their area, and
**86.8% of every negative label was never imaged**. The table contains no
missing values at all. So the model has been trained, tuned and scored against a
negative class that is mostly days nobody looked at.

Those figures are stated against the model's own target, flooding over more than
0.5% of district area. Measured instead against any standing water at all the
fabricated share reads 96.9%, but that number is misleading: Punjab is rice
paddy and is deliberately under water for much of the monsoon, so "any wet
pixel" flags 85% of fully-imaged district-days and is not a flood signal.

This rebuild joins the footprint cache and emits what was actually known:

    observed        imaged across >= 95% of the district; the value stands
    partial         imaged in part; a flood detection still counts, dryness
                    does not, because the dry part may be the unimaged part
    not_observed    no acquisition; value is NaN
    era_unreliable  before 2022 the footprint layer answers "everything, every
                    day" for 749 of 749 days, which is not an acquisition
                    pattern. Observability cannot be established there, so the
                    original value is kept and flagged rather than either
                    trusted or silently discarded. That choice belongs to the
                    analysis, not to this script.
    no_probe        the service was never asked

Positives and negatives are treated differently on purpose. Seeing water across
part of a district is a real detection regardless of what the rest of it was
doing; seeing no water across part of a district says nothing about the rest.
Asymmetric evidence deserves asymmetric handling.

Run: python -m pipeline.build_daily_observability
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DAILY = DATA / "gfm_district_daily_2015_2025.csv"
FOOTPRINT = DATA / "gfm_footprint_daily.csv"
OUT = DATA / "gfm_district_daily_observed_2015_2025.csv"

# Matches MIN_OBSERVED_FRACTION in sailaab/nowcast.py.
MIN_OBSERVED = 0.95
RELIABLE_FROM = "2022-01-01"
# Matches THRESHOLD in pipeline/run_forecaster_daily.py: the model's target is
# flooding over more than 0.5% of district area, not any standing water.
TARGET_FRACTION = 0.005

# 2022-07-14..18 is a five-day run of exactly 1.000 coverage sitting inside
# otherwise-partial data, which looks like the pre-2022 "everything" behaviour
# briefly returning rather than five consecutive full-state acquisitions. A
# hundred district-days is not worth the risk of treating a measurement
# artefact as ground truth.
SUSPECT_FULL_COVERAGE = {
    "2022-07-14", "2022-07-15", "2022-07-16", "2022-07-17", "2022-07-18",
}


def classify(row) -> str:
    """What was actually known about this district on this day."""
    if row["date"] in SUSPECT_FULL_COVERAGE:
        return "era_unreliable"
    if row["date"] < RELIABLE_FROM:
        return "era_unreliable"
    frac = row.get("acq_fraction")
    if pd.isna(frac):
        return "no_probe"
    if frac >= MIN_OBSERVED:
        return "observed"
    if frac > 0.0:
        return "partial"
    return "not_observed"


def main() -> int:
    if not FOOTPRINT.exists():
        sys.exit(f"missing {FOOTPRINT}; run `python -m pipeline.fetch_footprint_cache`")

    daily = pd.read_csv(DAILY)
    daily["date"] = daily["date"].astype(str)
    fp = pd.read_csv(FOOTPRINT, usecols=["date", "district", "acq_fraction"])
    fp["date"] = fp["date"].astype(str)

    # The cache is append-only and resumable, and a lock failure once let two
    # fetchers run at the same time, so the same district-day can appear twice.
    # Duplicates have always agreed, which makes dropping them lossless, but a
    # silent row-count explosion in the join is exactly the kind of thing that
    # produces a confidently wrong table, so disagreement is a hard error.
    clash = fp.groupby(["date", "district"])["acq_fraction"].nunique()
    conflicting = clash[clash > 1]
    if len(conflicting):
        sys.exit(
            f"{len(conflicting)} district-days have conflicting footprint values; "
            "the cache cannot be deduplicated safely, refetch them"
        )
    before = len(fp)
    fp = fp.drop_duplicates(subset=["date", "district"], keep="first")
    if before != len(fp):
        print(f"footprint cache: dropped {before - len(fp):,} duplicate rows "
              f"(all in agreement)")

    df = daily.merge(fp, on=["date", "district"], how="left")
    if len(df) != len(daily):
        sys.exit(f"join changed row count {len(daily)} -> {len(df)}; duplicate keys?")

    df["observability"] = df.apply(classify, axis=1)

    # A detection survives partial coverage; an absence does not.
    #
    # "Detection" means the model's own target, fraction above 0.5% of district
    # area, not any flood pixel at all. Punjab is rice paddy and is deliberately
    # under water for much of the monsoon, so "any wet pixel" marks 85% of
    # fully-imaged district-days as flooded and is not a flood signal. Using it
    # here understated the usable negatives by a factor of five.
    wet = df["fraction"].fillna(0.0) > TARGET_FRACTION
    keep = (
        (df["observability"] == "observed")
        | (df["observability"] == "era_unreliable")
        | ((df["observability"] == "partial") & wet)
    )
    df["label_usable"] = keep
    for col in ("flooded_ha", "fraction"):
        df[f"{col}_raw"] = df[col]
        df.loc[~keep, col] = np.nan

    df.to_csv(OUT, index=False)

    # What the rebuild actually did, stated in the terms that matter.
    rel = df[df["observability"].isin(["observed", "partial", "not_observed", "no_probe"])]
    pos_raw = rel["fraction_raw"] > TARGET_FRACTION
    neg_raw = (~pos_raw) & rel["fraction_raw"].notna()
    old_dry = int(neg_raw.sum())
    new_dry = int((neg_raw & (rel["observability"] == "observed")).sum())
    old_wet = int(pos_raw.sum())
    new_wet = int(rel["label_usable"].loc[pos_raw].sum())

    print(f"wrote {OUT}  ({len(df):,} rows)")
    print()
    print("observability of every district-day:")
    for state, n in df["observability"].value_counts().items():
        print(f"  {state:<16}{n:>8,}  ({n / len(df):>6.1%})")
    print()
    print(f"reliable era only ({len(rel):,} district-days, 2022 onward):")
    print(f"  negatives  {old_dry:>7,}  ->  {new_dry:>6,}"
          f"   ({1 - new_dry / max(old_dry, 1):.1%} were never imaged)")
    print(f"  positives  {old_wet:>7,}  ->  {new_wet:>6,}"
          f"   ({1 - new_wet / max(old_wet, 1):.1%} dropped)")
    print(f"  now missing {int(rel['flooded_ha'].isna().sum()):,} of {len(rel):,}")
    print()
    print("The old table had zero missing values across the whole record.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
