# tests/test_windows.py
from sailaab.windows import monsoon_windows


def test_first_window_starts_on_season_start():
    w = monsoon_windows(2025)
    assert w[0] == ("2025-06-15", "2025-06-25")


def test_windows_are_contiguous_and_ordered():
    w = monsoon_windows(2025)
    for (a, b), (c, d) in zip(w, w[1:]):
        assert b == c and a < b


def test_final_window_truncates_at_season_end():
    w = monsoon_windows(2025)
    assert w[-1][1] == "2025-09-30"
    # Jun 15 -> Sep 30 = 107 days = 10 full 10-day windows + 7-day remainder
    assert len(w) == 11


def test_respects_custom_window_length():
    w = monsoon_windows(2025, window_days=30)
    assert len(w) == 4  # 30+30+30+17
    assert w[-1] == ("2025-09-13", "2025-09-30")
