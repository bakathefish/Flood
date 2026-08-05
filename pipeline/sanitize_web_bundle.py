# pipeline/sanitize_web_bundle.py
"""Strip third-party vendor names out of the shipped web bundle.

The design-system dependency ships its translator-note metadata inside the
production bundle. Those ``description`` fields are notes for whoever writes the
translations; they are never rendered. One of them uses a vendor name as an
example of a citation label, which then appears verbatim in the published
JavaScript even though nothing on the page ever shows it.

This rewrites those example strings to neutral wording. Only non-rendering
metadata is touched, never a ``defaultMessage`` or any string the interface
displays. ``tests/test_site.py`` asserts the shipped bundle stays clean, so a
rebuild that skips this step fails the suite rather than silently republishing.

Run after building into docs/:
    python -m pipeline.sanitize_web_bundle
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"

# (needle, replacement). Needles are vendor examples inside i18n `description`
# metadata; replacements keep the sentence readable for a translator.
REPLACEMENTS = [
    ("Citation 1: OpenAI research paper", "Citation 1: a research paper"),
]

# Vendor branding that must not survive in the shipped bundle.
FORBIDDEN = ("OpenAI",)


def sanitize(text: str) -> str:
    for needle, repl in REPLACEMENTS:
        text = text.replace(needle, repl)
    return text


def main() -> None:
    if not ASSETS.is_dir():
        raise SystemExit(f"no built assets at {ASSETS}; run the site build first")

    touched = 0
    for path in sorted(ASSETS.glob("*.js")):
        original = path.read_text(encoding="utf-8", errors="surrogatepass")
        cleaned = sanitize(original)
        if cleaned != original:
            path.write_text(cleaned, encoding="utf-8", errors="surrogatepass")
            touched += 1
            print(f"sanitized {path.name}")

    leftovers = []
    for path in sorted(ASSETS.glob("*.js")):
        text = path.read_text(encoding="utf-8", errors="surrogatepass")
        for name in FORBIDDEN:
            if name in text:
                leftovers.append(f"{path.name}: {name}")

    print(f"files rewritten: {touched}")
    if leftovers:
        raise SystemExit("vendor names still present: " + "; ".join(leftovers))
    print("bundle clean")


if __name__ == "__main__":
    main()
