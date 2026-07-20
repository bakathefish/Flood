# tests/test_decade.py
from sailaab.decade import run_manifest


def test_manifest_covers_all_years_and_windows():
    m = run_manifest([2023, 2025])
    assert {r["year"] for r in m} == {2023, 2025}
    assert all(r["export_name"].startswith("sailaab_decade_") for r in m)
    r0 = [r for r in m if r["year"] == 2023][0]
    assert r0["window"] == ("2023-06-15", "2023-06-25")
    assert r0["pre"] == ("2023-04-01", "2023-05-31")


def test_manifest_export_names_unique():
    m = run_manifest([2015, 2016])
    names = [r["export_name"] for r in m]
    assert len(names) == len(set(names))
