# tests/test_alerts.py
import pytest

from sailaab.alerts import render_alert


def test_english_alert_contains_facts():
    s = render_alert("Gurdaspur", flooded_km2=142.7, trend="rising", lang="en")
    assert "Gurdaspur" in s and "142.7" in s and "rising" in s and "1070" in s


def test_punjabi_alert_renders_gurmukhi():
    s = render_alert("Gurdaspur", flooded_km2=142.7, trend="rising", lang="pa")
    assert "ਹੜ੍ਹ" in s  # "flood" in Gurmukhi
    assert "142.7" in s and "1070" in s


def test_hindi_alert_renders_devanagari():
    s = render_alert("Gurdaspur", flooded_km2=10.0, trend="falling", lang="hi")
    assert "बाढ़" in s and "10.0" in s


def test_unknown_language_raises():
    with pytest.raises(ValueError, match="lang"):
        render_alert("Moga", 1.0, "stable", lang="fr")


def test_trend_is_translated_not_english_leaked():
    s = render_alert("Moga", 1.0, "rising", lang="pa")
    assert "rising" not in s
