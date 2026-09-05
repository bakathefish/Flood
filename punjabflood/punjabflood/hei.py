"""The headroom-exhaustion index.

For a dam with live storage ``S`` and live capacity ``K``, a forecast of daily inflow
volumes ``I_1..I_H`` (BCM) and a non-spill passing capacity ``A`` (turbines and outlets,
BCM/day), the index over horizon ``H`` days is

    HEI_H = (sum(I) - (K - S) - A * H) / K

Positive means the reservoir cannot absorb the forecast inflow without opening the
spillway within ``H`` days; the forced release is the volume that has to be passed above
``A`` once the reservoir is full. The day-by-day water balance gives the day of
exhaustion and the release hydrograph; a full reservoir must pass its inflow.

This is a bound on the operator, not a prediction of the operator: BBMB may release
earlier and more gently (as in 2025), which shows up as arrivals before the predicted day
and lower peaks. The verification module scores both timing and magnitude.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from punjabflood import constants as C


@dataclass
class HEIResult:
    dam: str
    horizon_days: int
    storage_bcm: float
    capacity_bcm: float
    headroom_bcm: float
    inflow_volume_bcm: float
    absorption_bcm_per_day: float
    hei: float
    forced_release_bcm: float
    day_of_exhaustion: int | None  # 1-based day within the horizon, None if not reached
    release_by_day_cusecs: list[float]  # mean forced release per day (0 before exhaustion)
    storage_by_day_bcm: list[float]

    def to_dict(self) -> dict:
        return asdict(self)


def absorption_cusecs(dam: str, canal_draw_cusecs: float | None = None) -> float:
    """Non-spill passing capacity used in the index: the dam's turbine passage as recorded
    in ``constants`` (Bhakra derived from the ESDD total passage, Pong from the EAP, Ranjit
    Sagar estimated from installed power and head; see the ``Sourced`` notes there).
    ``canal_draw_cusecs`` is accepted for callers that want the river-only passage and is
    subtracted when given."""
    d = C.DAMS[dam]
    if d.turbine_capacity_cusecs is None:
        raise ValueError(f"{dam}: no documented non-spill passing capacity; pass one explicitly")
    return max(d.turbine_capacity_cusecs.value - (canal_draw_cusecs or 0.0), 0.0)


def headroom_exhaustion(
    dam: str,
    storage_bcm: float,
    daily_inflow_bcm,
    absorption_cusecs_value: float,
    capacity_bcm: float | None = None,
) -> HEIResult:
    cap = capacity_bcm if capacity_bcm is not None else C.DAMS[dam].live_capacity_bcm.value
    inflow = np.asarray(list(daily_inflow_bcm), dtype=float)
    H = len(inflow)
    a = C.cusec_days_to_bcm(absorption_cusecs_value)
    headroom = max(cap - storage_bcm, 0.0)
    total = float(inflow.sum())
    hei = (total - headroom - a * H) / cap if H > 0 else float("nan")

    s = min(storage_bcm, cap)
    release_by_day = []
    storage_by_day = []
    day_ex = None
    forced_total = 0.0
    for d, i_d in enumerate(inflow, start=1):
        s = s + i_d - a
        if s > cap:
            excess = s - cap
            s = cap
            if day_ex is None:
                day_ex = d
        else:
            excess = 0.0
        s = max(s, 0.0)
        forced_total += excess
        release_by_day.append(C.bcm_to_cusec_days(excess))
        storage_by_day.append(s)
    return HEIResult(
        dam=dam,
        horizon_days=H,
        storage_bcm=float(storage_bcm),
        capacity_bcm=float(cap),
        headroom_bcm=float(headroom),
        inflow_volume_bcm=total,
        absorption_bcm_per_day=float(a),
        hei=float(hei),
        forced_release_bcm=float(forced_total),
        day_of_exhaustion=day_ex,
        release_by_day_cusecs=[float(x) for x in release_by_day],
        storage_by_day_bcm=[float(x) for x in storage_by_day],
    )


def ensemble_summary(results: list[HEIResult]) -> dict:
    """Probability of exhaustion within the horizon and quantiles of the index and the
    peak daily forced release across ensemble members."""
    if not results:
        return {}
    heis = np.array([r.hei for r in results])
    peaks = np.array(
        [max(r.release_by_day_cusecs) if r.release_by_day_cusecs else 0.0 for r in results]
    )
    ex = np.array([r.day_of_exhaustion is not None for r in results])
    days = [r.day_of_exhaustion for r in results if r.day_of_exhaustion is not None]
    return {
        "n_members": len(results),
        "p_exhaustion": float(ex.mean()),
        "hei_q10": float(np.quantile(heis, 0.1)),
        "hei_q50": float(np.quantile(heis, 0.5)),
        "hei_q90": float(np.quantile(heis, 0.9)),
        "peak_release_q50_cusecs": float(np.quantile(peaks, 0.5)),
        "peak_release_q90_cusecs": float(np.quantile(peaks, 0.9)),
        "median_day_of_exhaustion": float(np.median(days)) if days else None,
    }


def error_paths(
    n_days: int, n_draws: int, sd_bcm: float, acf1: float, rng: np.random.Generator
) -> np.ndarray:
    """``n_draws`` error paths over ``n_days`` from a stationary AR(1) process with standard
    deviation ``sd_bcm`` and day-to-day autocorrelation ``acf1`` (nan is taken as zero)."""
    phi = 0.0 if acf1 != acf1 else float(min(max(acf1, -0.99), 0.99))
    z = rng.standard_normal((n_draws, n_days))
    e = np.empty_like(z)
    e[:, 0] = z[:, 0]
    for d in range(1, n_days):
        e[:, d] = phi * e[:, d - 1] + np.sqrt(1.0 - phi * phi) * z[:, d]
    return sd_bcm * e


def _balance_matrix(storage_bcm: float, cap: float, a: float, inflow: np.ndarray):
    """The water balance of ``headroom_exhaustion`` run on a matrix of inflow paths
    (paths by days). Returns the exhaustion flag and the peak daily forced release (cusecs)
    per path."""
    n = inflow.shape[0]
    s = np.full(n, min(storage_bcm, cap), dtype=float)
    peak = np.zeros(n)
    exhausted = np.zeros(n, dtype=bool)
    for d in range(inflow.shape[1]):
        s = s + inflow[:, d] - a
        excess = np.maximum(s - cap, 0.0)
        exhausted |= s > cap
        s = np.clip(s, 0.0, cap)
        peak = np.maximum(peak, excess)
    return exhausted, C.bcm_to_cusec_days(peak)


def ensemble_summary_with_error(
    dam: str,
    storage_bcm: float,
    member_inflows,
    absorption_cusecs_value: float,
    sd_bcm: float,
    acf1: float,
    n_draws: int = 200,
    seed: int = 0,
    capacity_bcm: float | None = None,
) -> dict:
    """Probability of exhaustion and forced-release quantiles when the inflow model's own
    error is sampled on top of every QPF member.

    The error is additive on the daily inflow volume, Gaussian, with the calibration RMSE as
    its standard deviation and the residual lag-1 autocorrelation as its persistence
    (``error_paths``); ``n_draws`` paths per member, perturbed inflows floored at zero. The
    RMSE is measured on the ordinary filling days the model was fitted on, so this is the
    model's ordinary-day error, not its flood-scale error, and the widened probability is
    still an inner estimate of the uncertainty. Seeded, so a product is reproducible. Empty
    when ``sd_bcm`` is not a non-negative number or there are no members."""
    members = [np.asarray(m, dtype=float) for m in member_inflows]
    members = [m for m in members if len(m)]
    if not members or sd_bcm != sd_bcm or sd_bcm < 0:
        return {}
    cap = capacity_bcm if capacity_bcm is not None else C.DAMS[dam].live_capacity_bcm.value
    a = C.cusec_days_to_bcm(absorption_cusecs_value)
    rng = np.random.default_rng(seed)
    ex_all, peak_all = [], []
    for m in members:
        paths = np.maximum(m[None, :] + error_paths(len(m), n_draws, sd_bcm, acf1, rng), 0.0)
        ex, peak = _balance_matrix(storage_bcm, cap, a, paths)
        ex_all.append(ex)
        peak_all.append(peak)
    ex = np.concatenate(ex_all)
    peak = np.concatenate(peak_all)
    return {
        "p_exhaustion_model_error": float(ex.mean()),
        "peak_release_q50_model_error_cusecs": float(np.quantile(peak, 0.5)),
        "peak_release_q90_model_error_cusecs": float(np.quantile(peak, 0.9)),
        "n_error_draws": int(n_draws),
        "error_sd_bcm_per_day": float(sd_bcm),
        "error_acf1": None if acf1 != acf1 else float(acf1),
    }
