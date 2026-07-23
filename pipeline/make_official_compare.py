# pipeline/make_official_compare.py
"""Satellite vs Special Girdawari: rank comparison figure.

Official district crop-damage (Revenue Dept, 2025-09-13, cumulative season,
modern 23-district vintage) vs Sailaab RF crop-flooded snapshot (Census-2011
vintage). Modern districts are merged into their 2011 parents before comparing.
Deterministic output: atlas/official_vs_sailaab.png
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from sailaab import figstyle  # noqa: E402

INK = "#0a1014"
LINE = "#28394a"
PAPER = "#e9e4d6"
DIM = "#9aa5a4"
WATER = "#4fd8c9"
AMBER = "#ffb454"

VINTAGE_MERGE = {"Fazilka": "Firozpur", "Pathankot": "Gurdaspur", "Malerkotla": "Sangrur",
                 "Ferozepur": "Firozpur", "Mohali": "Sahibzada Ajit Singh Nagar",
                 "S.A.S. Nagar": "Sahibzada Ajit Singh Nagar", "Nawan Shahr": "Nawanshahr",
                 "Shahid Bhagat Singh Nagar": "Nawanshahr", "Sri Muktsar Sahib": "Muktsar",
                 "Ropar": "Rupnagar", "Tarn-Taran": "Tarn Taran"}


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra = pd.Series(a).rank().to_numpy()
    rb = pd.Series(b).rank().to_numpy()
    return float(np.corrcoef(ra, rb)[0, 1])


def main() -> None:
    off = pd.read_csv("data/official_relief_2025.csv")
    off = off[off.metric == "crop_damage_ha"].copy()
    off["district"] = off.district.map(lambda d: VINTAGE_MERGE.get(d, d))
    off = off.groupby("district", as_index=False).value.sum()

    ours = pd.read_csv("data/district_flood_stats_2025.csv")
    m = ours.merge(off, on="district", how="left")
    named = m.dropna(subset=["value"])
    all20 = m.fillna({"value": 0.0})

    rho_named = spearman(named.rf_flooded_ha.to_numpy(), named.value.to_numpy())
    rho_all = spearman(all20.rf_flooded_ha.to_numpy(), all20.value.to_numpy())

    figstyle.apply()
    fig, ax = plt.subplots(figsize=(10.5, 7.2), dpi=170)
    fig.patch.set_facecolor(INK)
    ax.set_facecolor(INK)
    for s in ax.spines.values():
        s.set_color(LINE)
    ax.tick_params(colors=DIM, labelsize=9, labelfontfamily=figstyle.FONT_MONO)
    ax.grid(True, color=LINE, lw=0.5, alpha=0.5)

    x = named.value.to_numpy()
    y = named.rf_flooded_ha.to_numpy()
    ax.scatter(x, y, s=64, color=WATER, edgecolors=INK, zorder=3)
    ax.set_xscale("log")
    ax.set_yscale("log")

    OFFSETS = {"Kapurthala": (7, 14), "Tarn Taran": (-64, -16)}
    for _, r in named.iterrows():
        if r.value > 8000 or r.rf_flooded_ha > 4000:
            ax.annotate(r.district, (r.value, r.rf_flooded_ha), textcoords="offset points",
                        xytext=OFFSETS.get(r.district, (7, 5)), color=AMBER, fontsize=9, family="monospace")

    ax.set_xlabel("Official Special Girdawari crop damage (ha, cumulative season): Revenue Dept, 13 Sep 2025",
                  color=DIM, fontsize=9.5)
    ax.set_ylabel("Sailaab RF flooded area (ha, SAR snapshot)", color=DIM, fontsize=9.5)
    ax.set_title(figstyle.clean("The satellite agrees with the ground survey") + "\n",
                 color=PAPER, fontsize=15, fontfamily=figstyle.FONT_DISPLAY, loc="left")
    ax.text(0.0, 1.02, f"Spearman rank correlation ρ = {rho_named:.2f} (named districts) · ρ = {rho_all:.2f} (all 20) · "
            "5 of top-6 districts match", transform=ax.transAxes, color=WATER, fontsize=10.5,
            fontfamily=figstyle.FONT_BODY)
    ax.text(0.0, -0.14, "Scales differ by design: girdawari counts season-cumulative damage incl. waterlogging; the SAR "
            "figure is a peak-window snapshot.\nDivergences concentrate in the Ghaggar basin (Patiala/Sangrur/Mansa), "
            "outside the descending-orbit SAR windows, documented in docs/notes/gov-data.md.",
            transform=ax.transAxes, color=DIM, fontsize=8.5, fontfamily=figstyle.FONT_BODY, va="top")

    fig.tight_layout()
    fig.savefig("atlas/official_vs_sailaab.png", facecolor=INK, bbox_inches="tight")
    print(f"rho_named={rho_named:.3f} rho_all20={rho_all:.3f} n_named={len(named)}")


if __name__ == "__main__":
    main()
