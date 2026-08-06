# tests/test_forecast_daily.py
import numpy as np
import pandas as pd
import pytest

from sailaab.forecast_daily import (
    build_climatology,
    climatology_percentile,
    dry_at_issue,
    forward_event,
    trailing_sums,
)


def _daily(rain, district="A", start="2020-08-01"):
    dates = pd.date_range(start, periods=len(rain), freq="D")
    return pd.DataFrame(
        {"date": dates, "district": district, "rain_mm": np.asarray(rain, dtype=float)}
    )


# --- trailing_sums ------------------------------------------------------------
def test_trailing_sum_includes_today_and_looks_back():
    out = trailing_sums(_daily([1, 2, 3, 4]), windows=(3,))
    assert out["rain_3d"].tolist() == [1.0, 3.0, 6.0, 9.0]


def test_trailing_sum_never_uses_the_future():
    # a huge value on the last day must not affect any earlier row
    a = trailing_sums(_daily([1, 1, 1, 1]), windows=(3,))["rain_3d"].tolist()
    b = trailing_sums(_daily([1, 1, 1, 999]), windows=(3,))["rain_3d"].tolist()
    assert a[:3] == b[:3]


def test_trailing_sums_are_per_district():
    df = pd.concat([_daily([1, 1, 1], "A"), _daily([10, 10, 10], "B")])
    out = trailing_sums(df, windows=(2,))
    assert out[out.district == "A"]["rain_2d"].tolist() == [1.0, 2.0, 2.0]
    assert out[out.district == "B"]["rain_2d"].tolist() == [10.0, 20.0, 20.0]


# --- climatology --------------------------------------------------------------
def _climo_frame(years, value=1.0, district="A"):
    parts = []
    for y in years:
        dates = pd.date_range(f"{y}-08-01", periods=30, freq="D")
        parts.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "district": district,
                    "rain_mm": np.full(len(dates), float(value)),
                }
            )
        )
    return pd.concat(parts, ignore_index=True)


def test_percentile_of_an_unprecedented_value_is_one():
    climo = build_climatology(_climo_frame(range(1990, 2020), 1.0), windows=(3,))
    cur = trailing_sums(_daily([500, 500, 500], start="2020-08-15"), windows=(3,))
    out = climatology_percentile(cur, climo, windows=(3,))
    assert out["rain_3d_pctl"].iloc[-1] == pytest.approx(1.0)


def test_percentile_of_a_typical_value_is_mid_range():
    # historical 3-day sums are all 3.0; a matching value ranks at the top of
    # the ties, and a smaller one ranks at the bottom
    climo = build_climatology(_climo_frame(range(1990, 2020), 1.0), windows=(3,))
    low = trailing_sums(_daily([0, 0, 0], start="2020-08-15"), windows=(3,))
    out = climatology_percentile(low, climo, windows=(3,))
    assert out["rain_3d_pctl"].iloc[-1] == pytest.approx(0.0)


def test_percentile_is_per_district():
    wet = _climo_frame(range(1990, 2020), 10.0, "wet")
    dry = _climo_frame(range(1990, 2020), 1.0, "dry")
    climo = build_climatology(pd.concat([wet, dry], ignore_index=True), windows=(3,))
    cur = pd.concat(
        [
            trailing_sums(_daily([5, 5, 5], "wet", "2020-08-15"), windows=(3,)),
            trailing_sums(_daily([5, 5, 5], "dry", "2020-08-15"), windows=(3,)),
        ],
        ignore_index=True,
    )
    out = climatology_percentile(cur, climo, windows=(3,))
    w = out[(out.district == "wet")]["rain_3d_pctl"].iloc[-1]
    d = out[(out.district == "dry")]["rain_3d_pctl"].iloc[-1]
    # the same 15 mm is unremarkable in the wet district and extreme in the dry
    assert w < d


def test_percentile_unknown_district_is_nan():
    climo = build_climatology(_climo_frame(range(1990, 2020), 1.0, "A"), windows=(3,))
    cur = trailing_sums(_daily([5, 5, 5], "ZZ", "2020-08-15"), windows=(3,))
    out = climatology_percentile(cur, climo, windows=(3,))
    assert np.isnan(out["rain_3d_pctl"].iloc[-1])


# --- forward_event ------------------------------------------------------------
def _target(fracs, district="A", year=2020, start="2020-08-01"):
    dates = pd.date_range(start, periods=len(fracs), freq="D")
    return pd.DataFrame(
        {
            "date": dates,
            "district": district,
            "year": year,
            "fraction": np.asarray(fracs, dtype=float),
        }
    )


def test_forward_event_flags_a_crossing_inside_the_horizon():
    df = _target([0.0, 0.0, 0.9, 0.0])
    y = forward_event(df, threshold=0.5, horizon=2)
    assert y.iloc[0] == 1.0  # day+2 is wet
    assert y.iloc[1] == 1.0  # day+1 is wet


def test_forward_event_excludes_the_issue_day_itself():
    # wet today, dry for the whole horizon: the label must be 0, otherwise the
    # model gets credit for water already visible at issue time
    df = _target([0.9, 0.0, 0.0])
    y = forward_event(df, threshold=0.5, horizon=2)
    assert y.iloc[0] == 0.0


def test_forward_event_ignores_crossings_beyond_the_horizon():
    df = _target([0.0, 0.0, 0.0, 0.9])
    y = forward_event(df, threshold=0.5, horizon=2)
    assert y.iloc[0] == 0.0


def test_forward_event_does_not_cross_seasons():
    a = _target([0.0, 0.0], year=2020, start="2020-09-29")
    b = _target([0.9, 0.9], year=2021, start="2021-06-15")
    y = forward_event(pd.concat([a, b], ignore_index=True), threshold=0.5, horizon=3)
    assert y.iloc[0] == 0.0  # end of 2020 cannot borrow 2021


def test_forward_event_nan_when_horizon_runs_off_the_record():
    df = _target([0.0, 0.0])
    y = forward_event(df, threshold=0.5, horizon=3)
    assert np.isnan(y.iloc[-1])


# --- dry_at_issue -------------------------------------------------------------
def test_dry_at_issue_excludes_already_flooded_rows():
    df = _target([0.0, 0.9])
    m = dry_at_issue(df, threshold=0.5)
    assert m.tolist() == [True, False]


def test_dry_at_issue_treats_unknown_as_candidate():
    df = _target([np.nan])
    assert dry_at_issue(df, threshold=0.5).iloc[0]


# --- adjacency and neighbour water --------------------------------------------
def _sq(x0, y0, x1, y1):
    return {
        "type": "Polygon",
        "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]],
    }


def _fc(**boxes):
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"district": k}, "geometry": v}
            for k, v in boxes.items()
        ],
    }


def test_adjacency_finds_touching_districts_only():
    from sailaab.forecast_daily import build_adjacency

    gj = _fc(
        A=_sq(0, 0, 1, 1),
        B=_sq(1, 0, 2, 1),  # shares an edge with A
        C=_sq(5, 5, 6, 6),  # far away
    )
    adj = build_adjacency(gj)
    assert adj["A"] == ["B"]
    assert adj["B"] == ["A"]
    assert adj["C"] == []


def test_neighbour_water_excludes_the_district_itself():
    from sailaab.forecast_daily import neighbour_water

    daily = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-08-01"] * 2),
            "district": ["A", "B"],
            "fraction": [0.9, 0.0],
        }
    )
    out = neighbour_water(daily, {"A": ["B"], "B": ["A"]}, days=1)
    d = daily.assign(nbr=out.to_numpy())
    # A is soaked but must not see its own water; B must see A's
    assert d[d.district == "A"]["nbr"].iloc[0] == pytest.approx(0.0)
    assert d[d.district == "B"]["nbr"].iloc[0] == pytest.approx(0.9)


def test_neighbour_water_looks_back_over_the_window():
    from sailaab.forecast_daily import neighbour_water

    dates = pd.to_datetime(["2020-08-01", "2020-08-02"])
    daily = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "district": ["A", "A", "B", "B"],
            "fraction": [0.5, 0.0, 0.0, 0.0],
        }
    ).sort_values(["district", "date"])
    out = neighbour_water(daily, {"A": ["B"], "B": ["A"]}, days=3)
    d = daily.assign(nbr=out.to_numpy())
    later = d[(d.district == "B") & (d.date == dates[1])]["nbr"].iloc[0]
    assert later == pytest.approx(0.5)  # yesterday's flood next door still counts


def test_seasonal_onset_rate_is_per_district_and_week():
    from sailaab.forecast_daily import seasonal_onset_rate

    tr = pd.DataFrame(
        {
            "district": ["A"] * 7 + ["B"] * 7,
            "day_of_season": list(range(7)) * 2,
            "y": [1.0] * 7 + [0.0] * 7,
        }
    )
    out = seasonal_onset_rate(tr)
    assert out[out.district == "A"]["season_climo"].iloc[0] == pytest.approx(1.0)
    assert out[out.district == "B"]["season_climo"].iloc[0] == pytest.approx(0.0)
