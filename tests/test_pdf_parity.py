# tests/test_pdf_parity.py
"""The shipped PDFs must say what their source pages say.

The site gates every JS chunk for retired claims, and it gates the HTML. It did
not gate the PDFs, and they are the most public artifact here: the README links
the synopsis twice and the app links it in all three languages.

The gap showed. `docs/synopsis-print.html` was corrected, the PDF beside it was
not regenerated, and for a day the download carried retracted wording
("hindcast risk", "hindcast P") along with the pooled average precision printed
without the delete-2025 figure that qualifies it. Every automated check passed
the whole time, because nothing read the PDF.

Regenerate with `python -m pipeline.render_pdfs` when these fail.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pypdfium2 = pytest.importorskip("pypdfium2", reason="PDF gate needs pypdfium2")

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

PAIRS = [
    ("synopsis-print.html", "SAILAAB-synopsis.pdf"),
    ("business-plan-print.html", "SAILAAB-business-plan.pdf"),
]


def _pdf_text(name: str) -> str:
    path = DOCS / name
    assert path.exists(), f"{name} is linked publicly but missing"
    doc = pypdfium2.PdfDocument(path)
    return "".join(doc[i].get_textpage().get_text_range() for i in range(len(doc)))


# Wording that belonged to a superseded model or a retracted evaluation. These
# are the exact strings that shipped inside the stale PDF.
RETIRED = [
    "hindcast risk",
    "hindcast P",
    "The result, and what it is not",
    "0.549",
    "96%",
    "28 alerts",
    "predicted probability",
]

# A document that owns up to its own retractions has to quote the numbers it
# retracted: the synopsis says the "96% alert precision" claim was withdrawn,
# and that sentence is the honest part. So the rule is not "never mention it",
# it is "never assert it". An occurrence counts as disclosure when withdrawal
# language sits beside it.
WITHDRAWN_NEAR = ("withdraw", "retract", "superseded", "no longer", "was wrong", "corrected")
WINDOW = 400


def _asserted(text: str, needle: str) -> list[str]:
    """Occurrences of `needle` that are NOT marked as withdrawn nearby."""
    bare, start = [], 0
    while (i := text.find(needle, start)) != -1:
        ctx = text[max(0, i - WINDOW): i + WINDOW].lower()
        if not any(w in ctx for w in WITHDRAWN_NEAR):
            bare.append(text[max(0, i - 90): i + 90].replace("\n", " "))
        start = i + len(needle)
    return bare


@pytest.mark.parametrize("pdf", [p for _, p in PAIRS])
@pytest.mark.parametrize("needle", RETIRED)
def test_retired_wording_not_asserted_in_pdf(pdf, needle):
    bare = _asserted(_pdf_text(pdf), needle)
    assert not bare, (
        f"{needle!r} asserted without a withdrawal note in {pdf}: {bare[:2]}; "
        "run python -m pipeline.render_pdfs"
    )


def test_pooled_figure_never_travels_alone_in_the_pdf():
    """0.249 is very largely one monsoon, so it may not appear unqualified.

    The same rule already guards the JS chunks. The PDF escaped it and published
    the pooled number with neither the delete-2025 figure nor the interval.
    """
    text = _pdf_text("SAILAAB-synopsis.pdf")
    if "0.249" not in text:
        pytest.skip("synopsis no longer quotes the pooled figure")
    assert "0.042" in text, "pooled AP printed without the delete-2025 figure beside it"
    assert "0.004" in text and "0.521" in text, "pooled AP printed without its interval"


@pytest.mark.parametrize("html,pdf", PAIRS, ids=[p for _, p in PAIRS])
def test_pdf_is_not_stale_against_its_source(html, pdf):
    """A PDF older than the page it was rendered from has drifted.

    Cheap, and it catches the whole class: correcting the copy without
    re-rendering is the only way this file goes wrong.
    """
    src, out = DOCS / html, DOCS / pdf
    assert src.exists() and out.exists()
    assert out.stat().st_mtime >= src.stat().st_mtime - 1, (
        f"{pdf} predates {html}; run python -m pipeline.render_pdfs"
    )


def test_headline_claims_survived_the_render():
    """Text extraction has to actually find the claims, not just fail to find
    the retired ones. A blank or image-only render would pass every check
    above while publishing nothing readable."""
    text = _pdf_text("SAILAAB-synopsis.pdf")
    assert len(text) > 5_000, "synopsis PDF has almost no extractable text"
    for needle in ("block bootstrap", "0.042", "Sailaab"):
        assert needle in text, f"{needle!r} missing from the rendered synopsis"
