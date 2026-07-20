# tests/test_ee_graphs.py
import pytest

ee = pytest.importorskip("ee")
pytestmark = pytest.mark.ee  # excluded by default (pytest.ini)


@pytest.fixture(scope="module")
def initialized():
    ee.Initialize()
    return True


def test_punjab_district_count(initialized):
    from sailaab.ee_graphs import punjab_districts

    n = punjab_districts().size().getInfo()
    assert 18 <= n <= 23


def test_flood_mask_graph_builds(initialized):
    from sailaab.ee_graphs import flood_mask_for_window, punjab_districts

    aoi = punjab_districts().union(1).geometry()
    img = flood_mask_for_window(
        aoi, ("2023-07-05", "2023-07-15"), ("2023-04-01", "2023-05-31")
    )
    assert img.bandNames().getInfo() == ["flood"]
