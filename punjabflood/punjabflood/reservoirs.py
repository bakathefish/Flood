"""Reservoir state: the CWC daily storage feed and the BBMB bulletins on one daily frame,
plus the level-to-storage rating each dam's own record implies.

Sources
* CWC feed (``cwc.py``): level in metres and live storage in BCM, daily, 1991 onward for
  Bhakra and Pong, from 2001 for Ranjit Sagar; the three BBMB-managed dams stop reporting
  on 2025-07-11.
* BBMB bulletins (``data/reference/bbmb/bulletins_2026.jsonl``): level in feet, inflow and
  outflow in cusecs, twice daily (as on 06:00 and 18:00 IST), Bhakra and Pong only. Storage
  is not printed, so it is read off the CWC-fitted rating. The sheets the Internet Archive
  holds from before the hourly capture (two of September 2025, four of 2026) are in
  ``bulletins_wayback.jsonl`` in the same schema (``scripts/wayback_bulletins.py``).
* Press supplement for August to September 2025 (levels in feet, storage where a percent
  full was reported) fills the CWC gap for that flood.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from punjabflood import constants as C

REF = Path(__file__).resolve().parents[1] / "data" / "reference"
CWC_PULL = Path("data/raw/cwc/cwc_daily.csv")
CWC_LEGACY = REF / "cwc" / "reservoirs_monsoon_2015_2025_legacy.csv"
SUPPLEMENT_2025 = REF / "cwc" / "reservoirs_2025_flood_supplement.csv"
BULLETINS = REF / "bbmb" / "bulletins_2026.jsonl"
BULLETINS_WAYBACK = REF / "bbmb" / "bulletins_wayback.jsonl"
BULLETIN_COLUMNS = [
    "as_on",
    "date",
    "dam",
    "level_ft",
    "level_m",
    "inflow_cusecs",
    "outflow_cusecs",
    "basis",
]
# the sheet's own date line: "as on 15.09.2025 at 6.00 PM" (2025) or "as on 24-06-2026 06:00 Hrs."
SHEET_AS_ON = re.compile(
    r"as on\s+(\d{2})[.-](\d{2})[.-](\d{4})\s+(?:at\s+)?(\d{1,2})[.:](\d{2})\s*(AM|PM|Hrs\.?)?",
    re.IGNORECASE,
)
SHEET_ROW = re.compile(r"^(Bhakra|Pong)\s+([\d.]+)\s+(\d+)\s+(\d+)\s*$", re.MULTILINE)

STATE_COLUMNS = [
    "date",
    "dam",
    "level_m",
    "storage_bcm",
    "inflow_cusecs",
    "outflow_cusecs",
    "basis",
]
MAX_RATING_RESID_BCM = 0.3  # a pair further than this from the rating is a stale or mistyped row
STALE_LEVEL_JUMP_M = 0.3  # a repeated storage with the level moved by more than this is stale
# Screening gate for mistyped levels, relative to each dam's full reservoir level: the feed
# has 100 m digit slips (a 405 m reading in a 500 m record). No dam here draws down 100 m
# below FRL or stands 10 m above it, so the gate never touches a real reading.
LEVEL_GATE_BELOW_FRL_M = 100.0
LEVEL_GATE_ABOVE_FRL_M = 10.0
MAX_RATING_PASSES = 200  # worst-first outlier removals in the rating fit


def level_gate_m(dam: str) -> tuple[float, float]:
    """Plausible level window (metres) for a dam's printed readings."""
    frl = C.DAMS[dam].frl_m.value
    return frl - LEVEL_GATE_BELOW_FRL_M, frl + LEVEL_GATE_ABOVE_FRL_M


def load_cwc(path: Path = CWC_PULL) -> pd.DataFrame:
    """Rows of the new pull (``cwc.COLUMNS``) or the legacy 2015-2025 file, normalised to
    ``date, dam, level_m, storage_bcm, basis='cwc'``."""
    df = pd.read_csv(path)
    if "level_value" in df.columns:  # legacy layout
        lvl = df["level_value"].astype(float)
        lvl = np.where(df["level_unit"].astype(str).str.lower().eq("ft"), lvl * C.FOOT_M, lvl)
        out = pd.DataFrame(
            {
                "date": pd.to_datetime(df["date"]),
                "dam": df["dam"],
                "level_m": lvl,
                "storage_bcm": df["storage_value"].astype(float),
            }
        )
    else:
        out = pd.DataFrame(
            {
                "date": pd.to_datetime(df["date"]),
                "dam": df["dam"],
                "level_m": df["level_m"].astype(float),
                "storage_bcm": df["storage_bcm"].astype(float),
            }
        )
    out["basis"] = "cwc"
    out = out.dropna(subset=["date"])
    # the feed prints NA for both level and storage on unreported days; drop those rows
    out = out[out["level_m"].notna() | out["storage_bcm"].notna()].sort_values(["dam", "date"])
    return out.drop_duplicates(["dam", "date"], keep="last").reset_index(drop=True)


def load_supplement(path: Path = SUPPLEMENT_2025) -> pd.DataFrame:
    df = pd.read_csv(path)
    lvl = df["level_value"].astype(float)
    lvl = np.where(df["level_unit"].astype(str).str.lower().eq("ft"), lvl * C.FOOT_M, lvl)
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df["date"]),
            "dam": df["dam"],
            "level_m": lvl,
            "storage_bcm": df["storage_value"].astype(float),
        }
    )
    out["basis"] = "press"
    return out.sort_values(["dam", "date"]).reset_index(drop=True)


def parse_sheet_text(text: str) -> dict:
    """The parsed fields of one BBMB ``res_data.pdf`` sheet from its extracted text:
    ``as_on_date`` (dd-mm-yyyy), ``as_on_time`` (HH:MM, 24-hour), and per dam the level in
    feet, inflow and outflow in cusecs and the printed row, plus ``as_on_key``. The sheets
    of 2025 print "as on 15.09.2025 at 6.00 PM"; those of 2026 "as on 24-06-2026 06:00 Hrs."."""
    m = SHEET_AS_ON.search(text)
    if not m:
        raise ValueError("no 'as on' line in the sheet")
    dd, mm, yyyy, hh, mi, suffix = m.groups()
    hour = int(hh)
    if suffix and suffix.upper() == "PM" and hour < 12:
        hour += 12
    if suffix and suffix.upper() == "AM" and hour == 12:
        hour = 0
    rec: dict = {"as_on_date": f"{dd}-{mm}-{yyyy}", "as_on_time": f"{hour:02d}:{mi}"}
    for dam, level, inflow, outflow in SHEET_ROW.findall(text):
        key = dam.lower()
        rec[f"{key}_level_ft"] = float(level)
        rec[f"{key}_inflow_cusecs"] = int(inflow)
        rec[f"{key}_outflow_cusecs"] = int(outflow)
        rec[f"{key}_row"] = f"{dam}  {level}  {inflow}  {outflow}"
    if "bhakra_level_ft" not in rec or "pong_level_ft" not in rec:
        raise ValueError("sheet rows for both dams not found")
    rec["as_on_key"] = f"{rec['as_on_date']} {rec['as_on_time']}"
    return rec


def load_bulletins(
    path: Path = BULLETINS, extra: tuple[Path, ...] = (BULLETINS_WAYBACK,)
) -> pd.DataFrame:
    """One row per bulletin per dam: ``as_on`` (naive IST timestamp), ``date``, ``dam``,
    ``level_m``, ``inflow_cusecs``, ``outflow_cusecs``, ``basis='bbmb'``, from ``path`` and
    from every file in ``extra`` that exists (the archived sheets). A sheet present in two
    files counts once."""
    rows = []
    for p in (path, *extra):
        p = Path(p)
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            d = r.get("as_on_date")
            if not d:
                continue
            dd, mm, yy = d.split("-")
            t = (r.get("as_on_time") or "00:00").replace(".", ":")
            as_on = pd.Timestamp(f"{yy}-{mm}-{dd} {t}")
            for key, dam in (("bhakra", "Bhakra"), ("pong", "Pong")):
                if r.get(f"{key}_level_ft") is None:
                    continue
                rows.append(
                    {
                        "as_on": as_on,
                        "date": as_on.normalize(),
                        "dam": dam,
                        "level_ft": float(r[f"{key}_level_ft"]),
                        "level_m": float(r[f"{key}_level_ft"]) * C.FOOT_M,
                        "inflow_cusecs": r.get(f"{key}_inflow_cusecs"),
                        "outflow_cusecs": r.get(f"{key}_outflow_cusecs"),
                        "basis": "bbmb",
                    }
                )
    if not rows:
        return pd.DataFrame(columns=BULLETIN_COLUMNS)
    df = pd.DataFrame(rows)
    return df.sort_values(["dam", "as_on"]).drop_duplicates(["dam", "as_on"]).reset_index(drop=True)


@dataclass
class Rating:
    """Monotone level-to-storage curve fitted on a dam's own (level, storage) pairs."""

    dam: str
    levels_m: np.ndarray
    storage_bcm: np.ndarray

    @classmethod
    def fit(
        cls, dam: str, level_m, storage_bcm, max_resid_bcm: float = MAX_RATING_RESID_BCM
    ) -> Rating:
        """Isotonic fit with worst-first outlier removal: while any pair sits more than
        ``max_resid_bcm`` from the monotone fit, the single worst pair is dropped and the
        curve refitted. The feed occasionally repeats the previous day's storage against a
        new level (a stale row); without this pass one such pair at a record level pulls the
        whole top of the curve down, and removing every large residual at once would also
        remove the sound top pairs the stale one had dragged the fit away from. Levels
        outside ``level_gate_m(dam)`` (digit slips) never enter the fit."""
        x = np.asarray(level_m, dtype=float)
        y = np.asarray(storage_bcm, dtype=float)
        ok = ~(np.isnan(x) | np.isnan(y))
        if dam in C.DAMS:
            lo, hi = level_gate_m(dam)
            ok &= (x >= lo) & (x <= hi)
        x, y = x[ok], y[ok]
        if len(x) < 10:
            raise ValueError(f"{dam}: only {len(x)} (level, storage) pairs; cannot fit a rating")
        for _ in range(MAX_RATING_PASSES):
            iso = IsotonicRegression(increasing=True, out_of_bounds="clip")
            iso.fit(x, y)
            resid = np.abs(y - iso.predict(x))
            worst = int(np.argmax(resid))
            if resid[worst] <= max_resid_bcm or len(x) <= 10:
                break
            x, y = np.delete(x, worst), np.delete(y, worst)
        grid = np.unique(x)
        return cls(dam, grid, iso.predict(grid))

    def storage(self, level_m) -> np.ndarray:
        """Storage in BCM; clamps to the observed level range (no vertical extrapolation)."""
        return np.interp(np.asarray(level_m, dtype=float), self.levels_m, self.storage_bcm)

    def level(self, storage_bcm) -> np.ndarray:
        return np.interp(np.asarray(storage_bcm, dtype=float), self.storage_bcm, self.levels_m)

    @property
    def level_range_m(self) -> tuple[float, float]:
        return float(self.levels_m[0]), float(self.levels_m[-1])


def fit_ratings(cwc: pd.DataFrame) -> dict[str, Rating]:
    out = {}
    for dam, g in cwc.groupby("dam"):
        try:
            out[dam] = Rating.fit(dam, g["level_m"], g["storage_bcm"])
        except ValueError:
            continue
    return out


def reconcile_cwc(
    cwc: pd.DataFrame,
    ratings: dict[str, Rating],
    tol_bcm: float = MAX_RATING_RESID_BCM,
    stale_jump_m: float = STALE_LEVEL_JUMP_M,
) -> pd.DataFrame:
    """Make each CWC row's storage consistent with its level.

    The level is the gauge reading; the storage is a table lookup the feed sometimes fails
    to update (the previous row's storage repeated against a new level) or mistypes. Rows
    whose storage is more than ``tol_bcm`` from the dam's rating at the printed level, or
    whose storage repeats the previous row while the level moved more than ``stale_jump_m``,
    take the rating's storage and ``basis='cwc_level'``. A level outside ``level_gate_m``
    is a mistyped level (the feed has 100 m digit slips): it is blanked and the storage
    kept, unless the storage is stale too, in which case both fields are untrustworthy and
    the row is dropped. A level above the fitted range but inside the gate (a record season)
    is kept and rated at the curve's top value. Rows without a rating pass unchanged."""
    out = []
    for dam, g in cwc.groupby("dam", sort=False):
        g = g.sort_values("date").copy()
        r = ratings.get(dam)
        if r is None:
            out.append(g)
            continue
        lvl = g["level_m"].to_numpy(dtype=float)
        sto = g["storage_bcm"].to_numpy(dtype=float)
        has_level = ~np.isnan(lvl)
        lo, hi = level_gate_m(dam) if dam in C.DAMS else r.level_range_m
        level_in_range = has_level & (lvl >= lo) & (lvl <= hi)
        rated = np.where(has_level, r.storage(np.where(has_level, lvl, lo)), np.nan)
        prev_sto = np.r_[np.nan, sto[:-1]]
        prev_lvl = np.r_[np.nan, lvl[:-1]]
        stale = (sto == prev_sto) & (np.abs(lvl - prev_lvl) > stale_jump_m)
        inconsistent = has_level & ~np.isnan(sto) & (np.abs(sto - rated) > tol_bcm)
        bad_level = has_level & ~level_in_range
        fix = (stale | inconsistent) & level_in_range
        drop = stale & bad_level
        g.loc[g.index[fix], "storage_bcm"] = rated[fix]
        g.loc[g.index[fix], "basis"] = "cwc_level"
        g.loc[g.index[bad_level & ~drop], "level_m"] = np.nan
        out.append(g[~drop])
    if not out:
        return cwc.copy()
    return pd.concat(out, ignore_index=True).sort_values(["dam", "date"]).reset_index(drop=True)


def daily_state(
    cwc: pd.DataFrame,
    bulletins: pd.DataFrame | None,
    ratings: dict[str, Rating],
    supplement: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """One row per dam per day. CWC storage where measured; otherwise storage from the
    rating applied to the day's latest bulletin level (or the press level). Inflow and
    outflow come from the day's latest bulletin when one exists."""
    parts = [cwc[["date", "dam", "level_m", "storage_bcm", "basis"]].copy()]
    if supplement is not None and len(supplement):
        sup = supplement.copy()
        for dam, g in sup.groupby("dam"):
            if dam in ratings:
                miss = g["storage_bcm"].isna()
                sup.loc[g.index[miss], "storage_bcm"] = ratings[dam].storage(g.loc[miss, "level_m"])
        parts.append(sup[["date", "dam", "level_m", "storage_bcm", "basis"]])
    flows = None
    if bulletins is not None and len(bulletins):
        latest = bulletins.sort_values("as_on").groupby(["dam", "date"]).tail(1)
        b = latest[["date", "dam", "level_m", "basis"]].copy()
        b["storage_bcm"] = np.nan
        for dam, g in b.groupby("dam"):
            if dam in ratings:
                b.loc[g.index, "storage_bcm"] = ratings[dam].storage(g["level_m"])
        parts.append(b)
        flows = latest[["date", "dam", "inflow_cusecs", "outflow_cusecs"]]
    allp = pd.concat(parts, ignore_index=True)
    prio = {"cwc": 0, "press": 1, "bbmb": 2}
    allp["prio"] = allp["basis"].map(prio) + allp["storage_bcm"].isna().astype(int) * 10
    state = (
        allp.sort_values(["dam", "date", "prio"])
        .groupby(["dam", "date"])
        .head(1)
        .drop(columns="prio")
    )
    if flows is not None:
        state = state.merge(flows, on=["date", "dam"], how="left")
    else:
        state["inflow_cusecs"] = np.nan
        state["outflow_cusecs"] = np.nan
    state = state[STATE_COLUMNS].sort_values(["dam", "date"]).reset_index(drop=True)
    return state


def headroom_bcm(storage_bcm, dam: str) -> np.ndarray:
    cap = C.DAMS[dam].live_capacity_bcm.value
    return np.maximum(cap - np.asarray(storage_bcm, dtype=float), 0.0)


def storage_fraction(storage_bcm, dam: str) -> np.ndarray:
    return np.asarray(storage_bcm, dtype=float) / C.DAMS[dam].live_capacity_bcm.value


def fill_gaps(state: pd.DataFrame, max_gap_days: int = 14) -> pd.DataFrame:
    """Linearly interpolate storage across short gaps (up to ``max_gap_days``) inside each
    dam's record, adding rows with ``basis='interp'``. Used so the sparse press points of
    August to September 2025 give a daily storage path for the event test; never
    extrapolates beyond the first or last observation."""
    out = []
    for dam, g in state.groupby("dam"):
        g = g.sort_values("date").set_index("date")
        full = pd.date_range(g.index.min(), g.index.max(), freq="D")
        r = g.reindex(full)
        r["dam"] = dam
        known = r["storage_bcm"].notna()
        # gap length for each missing day: distance between the bracketing observations
        obs_idx = np.flatnonzero(known.to_numpy())
        pos = np.arange(len(r))
        prev = np.searchsorted(obs_idx, pos, side="right") - 1
        nxt = np.searchsorted(obs_idx, pos, side="left")
        ok = (prev >= 0) & (nxt < len(obs_idx))
        gap = np.full(len(r), np.inf)
        gap[ok] = obs_idx[nxt[ok]] - obs_idx[prev[ok]]
        fillable = (~known.to_numpy()) & ok & (gap <= max_gap_days)
        interp = r["storage_bcm"].interpolate(method="linear", limit_area="inside")
        r.loc[fillable, "storage_bcm"] = interp[fillable]
        r.loc[fillable, "basis"] = "interp"
        r = r[r["storage_bcm"].notna()]
        r.index.name = "date"
        out.append(r.reset_index())
    res = pd.concat(out, ignore_index=True)
    return res[STATE_COLUMNS].sort_values(["dam", "date"]).reset_index(drop=True)
