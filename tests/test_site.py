# tests/test_site.py
"""Publish-gate contract for the built public site (docs/).

The public site is a React + Astryx single-page app: source lives in webapp/
and Vite builds it into docs/ for GitHub Pages, served under the /Flood/ base.
docs/index.html is therefore a thin shell (a #root div plus a hashed JS/CSS
bundle); the interactive logic lives inside the bundle, not in hand-authored
markup.

The monitor CI runs the whole test suite before it publishes ("never publish
from a red tree"). These tests are the site half of that gate: they don't
rebuild the app (the runner has no npm), they check that the committed docs/
artifacts are internally consistent and that every runtime data feed the app
loads is present and well-formed, so a half-deployed or data-broken site can
never ship silently.
"""

from __future__ import annotations

import csv
import json
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
INDEX = DOCS / "index.html"
ASSETS = DOCS / "assets"

BASE = "/Flood/"                    # GitHub Pages project-site base path
GEOJSON_BUDGET_BYTES = 150_000     # simplified district boundaries

# data feeds the SPA loads at runtime, with the columns each caller relies on
DATA_CSVS = {
    "district_flood_stats_2025.csv": ["district", "tierA_flooded_ha", "rf_flooded_ha"],
    "flood_frequency_districts_late_season.csv": ["district", "max_season_fraction"],
    "forecaster_2025_walkforward.csv": ["district", "date", "score"],
    "gfm_district_window_fractions_2015_2025.csv": ["year", "window_start", "district"],
}


class _Head(HTMLParser):
    """Collect <script>, <link> and <div> attributes from the shell."""

    def __init__(self):
        super().__init__()
        self.scripts: list[dict] = []
        self.links: list[dict] = []
        self.divs: list[dict] = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "script":
            self.scripts.append(d)
        elif tag == "link":
            self.links.append(d)
        elif tag == "div":
            self.divs.append(d)


def _parse() -> _Head:
    p = _Head()
    p.feed(INDEX.read_text(encoding="utf-8"))
    return p


def _as_local(url: str) -> Path:
    """Map a /Flood/... same-origin URL to its path under docs/."""
    assert url.startswith(BASE), f"asset {url!r} must be served under {BASE}"
    return DOCS / url[len(BASE):]


# --------------------------------------------------------------------------- #
# the shell: a valid SPA entry point that mounts the app
# --------------------------------------------------------------------------- #
def test_shell_exists_and_mounts_root():
    assert INDEX.exists(), "docs/index.html (built site) is missing"
    head = _parse()
    assert any(d.get("id") == "root" for d in head.divs), "shell has no #root mount"


def test_shell_metadata():
    html = INDEX.read_text(encoding="utf-8")
    assert "<title>Sailaab" in html, "title must name the project"
    assert 'name="description"' in html, "meta description missing (SEO/share cards)"
    assert 'name="theme-color"' in html, "theme-color missing"
    assert f'href="{BASE}favicon.svg"' in html, "favicon must be referenced under the base"


# --------------------------------------------------------------------------- #
# the bundle: shell points at a real, present, base-correct build
# --------------------------------------------------------------------------- #
def test_bundle_js_present_and_hashed():
    head = _parse()
    modules = [s["src"] for s in head.scripts
               if s.get("type") == "module" and s.get("src")]
    assert len(modules) == 1, f"expected exactly one entry module, found {modules}"
    src = modules[0]
    assert src.startswith(f"{BASE}assets/"), f"entry script not under {BASE}assets/: {src}"
    assert re.search(r"index-[A-Za-z0-9_-]+\.js$", src), "entry script is not a hashed build"
    p = _as_local(src)
    assert p.exists() and p.stat().st_size > 0, f"shell points at a missing JS bundle: {src}"


def test_bundle_css_present_and_hashed():
    head = _parse()
    sheets = [l["href"] for l in head.links
              if l.get("rel") == "stylesheet" and l.get("href")]
    assert len(sheets) == 1, f"expected exactly one stylesheet, found {sheets}"
    href = sheets[0]
    assert href.startswith(f"{BASE}assets/"), f"stylesheet not under {BASE}assets/: {href}"
    assert re.search(r"index-[A-Za-z0-9_-]+\.css$", href), "stylesheet is not a hashed build"
    p = _as_local(href)
    assert p.exists() and p.stat().st_size > 0, f"shell points at a missing CSS bundle: {href}"


def test_all_referenced_assets_use_the_base():
    # a stray root-relative asset (/assets/...) 404s on the project site
    head = _parse()
    urls = [s.get("src", "") for s in head.scripts] + [l.get("href", "") for l in head.links]
    for u in urls:
        if u.startswith("/") and not u.startswith(BASE):
            raise AssertionError(f"asset escapes the {BASE} base and will 404: {u}")


def test_nojekyll_present():
    # without it, GitHub Pages' Jekyll step can drop files and break asset serving
    assert (DOCS / ".nojekyll").exists(), "docs/.nojekyll missing (Pages may mangle assets)"
    assert (DOCS / "favicon.svg").exists(), "docs/favicon.svg missing"


# --------------------------------------------------------------------------- #
# runtime data feeds: present, same-origin, well-formed
# --------------------------------------------------------------------------- #
def test_district_geojson_is_simplified_and_complete():
    p = ASSETS / "punjab_districts.json"
    assert p.exists(), "docs/assets/punjab_districts.json missing (map has no boundaries)"
    assert p.stat().st_size <= GEOJSON_BUDGET_BYTES, (
        f"district geojson is {p.stat().st_size:,} B > {GEOJSON_BUDGET_BYTES:,} B; "
        "ship the simplified copy"
    )
    gj = json.loads(p.read_text(encoding="utf-8"))
    assert gj.get("type") == "FeatureCollection"
    assert len(gj["features"]) == 20, "Punjab has 20 mapped districts"
    assert all("district" in f["properties"] for f in gj["features"]), (
        "every feature needs a 'district' property to join the data feeds"
    )


def test_data_csvs_present_and_have_expected_columns():
    for name, required in DATA_CSVS.items():
        p = ASSETS / name
        assert p.exists(), f"data feed missing from the deploy: assets/{name}"
        with p.open(encoding="utf-8", newline="") as fh:
            reader = csv.reader(fh)
            header = next(reader, [])
            rows = sum(1 for _ in reader)
        for col in required:
            assert col in header, f"assets/{name} lost required column {col!r}"
        assert rows > 0, f"assets/{name} has a header but no data rows"


def test_shipped_bundle_carries_no_vendor_names():
    """The design-system dependency bundles translator-note metadata that names a
    third-party vendor as an example. Those notes are never rendered, but they do
    ship inside the published JavaScript. pipeline/sanitize_web_bundle.py
    rewrites them; this pins the result so a rebuild that skips that step fails
    here instead of republishing them."""
    forbidden = ("OpenAI",)
    bundles = sorted((DOCS / "assets").glob("*.js"))
    assert bundles, "no built JS bundle found in docs/assets"
    for path in bundles:
        text = path.read_text(encoding="utf-8", errors="surrogatepass")
        for name in forbidden:
            assert name not in text, f"{path.name} contains {name!r}"
