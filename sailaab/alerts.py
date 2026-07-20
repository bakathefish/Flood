# sailaab/alerts.py
"""Trilingual district flood alerts. 1070 = state disaster helpline.
Punjabi/Hindi copy: reviewed by a native reader before first public render
(plan 06 Task 5 checkpoint). Roadmap: Bhashini API for voice alerts."""

_TREND = {
    "en": {"rising": "rising", "falling": "falling", "stable": "stable"},
    "pa": {"rising": "ਵਧ ਰਿਹਾ", "falling": "ਘਟ ਰਿਹਾ", "stable": "ਸਥਿਰ"},
    "hi": {"rising": "बढ़ रहा", "falling": "घट रहा", "stable": "स्थिर"},
}

_TEMPLATES = {
    "en": (
        "FLOOD ALERT: ~{km2} sq km under water in {district} district "
        "(satellite-detected). Trend: {trend}. Helpline: 1070"
    ),
    "pa": (
        "ਹੜ੍ਹ ਚੇਤਾਵਨੀ: {district} ਜ਼ਿਲ੍ਹੇ ਵਿੱਚ ~{km2} ਵਰਗ ਕਿਲੋਮੀਟਰ ਖੇਤਰ ਪਾਣੀ ਹੇਠ ਹੈ "
        "(ਸੈਟੇਲਾਈਟ ਦੁਆਰਾ ਪਛਾਣਿਆ)। ਰੁਝਾਨ: {trend}। ਹੈਲਪਲਾਈਨ: 1070"
    ),
    "hi": (
        "बाढ़ चेतावनी: {district} जिले में ~{km2} वर्ग किमी क्षेत्र जलमग्न है "
        "(सैटेलाइट द्वारा पहचाना गया)। रुझान: {trend}। हेल्पलाइन: 1070"
    ),
}


def render_alert(
    district: str, flooded_km2: float, trend: str, lang: str = "pa"
) -> str:
    if lang not in _TEMPLATES:
        raise ValueError(f"unsupported lang: {lang}")
    return _TEMPLATES[lang].format(
        district=district, km2=round(flooded_km2, 1), trend=_TREND[lang][trend]
    )
