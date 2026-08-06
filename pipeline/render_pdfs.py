# pipeline/render_pdfs.py
"""Render the print HTML pages to the PDFs the site links.

These two PDFs are the most public thing the project ships: the README links
the synopsis twice and the site links it in all three languages. They are also
the easiest artifact to forget, because correcting the HTML does not touch them.

That is not hypothetical. The synopsis PDF sat two hours behind its own source
for a day while the corrected HTML shipped beside it, so the PDF went on
publishing retracted wording ("hindcast risk", "hindcast P") and the pooled
average precision without the delete-2025 figure that qualifies it. A reader who
clicked the link got the retracted version of the claim.

So regeneration gets a script instead of a remembered browser step, and
``tests/test_pdf_parity.py`` fails the build when a PDF drifts from its source.

Run: python -m pipeline.render_pdfs
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

PAGES = [
    ("synopsis-print.html", "SAILAAB-synopsis.pdf"),
    ("business-plan-print.html", "SAILAAB-business-plan.pdf"),
]

CHROME_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]


def _browser() -> str:
    for p in CHROME_CANDIDATES:
        if p.exists():
            return str(p)
    for name in ("google-chrome", "chromium", "chrome", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    raise SystemExit("no Chrome or Edge found to render the PDFs")


def render(browser: str, src: Path, out: Path) -> None:
    """Print one page, honouring its own @page rules and no browser chrome."""
    cmd = [
        browser,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--no-pdf-header-footer",
        # local @font-face files are same-origin under file://, but be explicit
        "--allow-file-access-from-files",
        "--virtual-time-budget=20000",   # let webfonts settle before printing
        f"--print-to-pdf={out}",
        src.as_uri(),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if not out.exists() or out.stat().st_size < 10_000:
        raise SystemExit(f"render produced nothing usable for {src.name}\n{r.stderr[:800]}")


def main() -> int:
    browser = _browser()
    print(f"rendering with {browser}")
    for html, pdf in PAGES:
        src, out = DOCS / html, DOCS / pdf
        if not src.exists():
            print(f"  skip {html}: missing")
            continue
        before = out.stat().st_size if out.exists() else 0
        render(browser, src, out)
        print(f"  {html} -> {pdf}  ({before:,} -> {out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
