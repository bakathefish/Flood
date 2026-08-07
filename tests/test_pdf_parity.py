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

import re
from pathlib import Path

import pytest

# NOT importorskip. pypdfium2 was a comment in requirements.txt rather than a
# dependency, so this module skipped in its entirety on both CI runners: 18
# assertions locally, one silent skip where it mattered. A gate written because
# nothing read the PDF must not be allowed to quietly not read the PDF.
import pypdfium2  # noqa: E402

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
# it is "never assert it".
#
# The first version of this rule looked 400 characters either side for any
# withdrawal word, which immunised 21% of the document. A review demonstrated
# the bypass by planting "The forecaster achieves 96% alert precision in
# operational use." 300 characters from an unrelated withdrawal sentence: the
# gate passed it, and passed nothing when the same sentence sat elsewhere.
#
# Scoping the exemption to the containing SENTENCE closed the distance bypass
# and immediately opened three cheaper ones, because the exemption is granted to
# the whole sentence while the question is whether THIS occurrence is the thing
# being withdrawn. Four words defeated it:
#
#   "The forecaster achieves 96% alert precision in operational use, a figure
#    no longer disputed."
#
# and a document with no sentence punctuation becomes one sentence, so a single
# trigger word anywhere immunises everything. A rule general enough to be
# bypassed that cheaply is doing more work than the problem needs.
#
# Exactly two sentences in this document need the exemption, so they are named.
# Rephrasing one breaks the build, which is the correct outcome: someone should
# look at a changed disclosure rather than have a pattern quietly re-approve it.
DISCLOSURES = (
    "an early claim of 96% alert precision at four alerts a season was withdrawn",
    "a retracted 96% precision headline",
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).lower()


def _asserted(text: str, needle: str) -> list[str]:
    """Occurrences of `needle` outside a named disclosure sentence."""
    flat = _norm(text)
    spans = []
    for phrase in DISCLOSURES:
        j = flat.find(phrase)
        while j != -1:
            spans.append((j, j + len(phrase)))
            j = flat.find(phrase, j + 1)

    bare, start = [], 0
    nn = needle.lower()
    while (i := flat.find(nn, start)) != -1:
        if not any(lo <= i < hi for lo, hi in spans):
            bare.append(flat[max(0, i - 90): i + 90])
        start = i + len(nn)
    return bare


ATTACKS = [
    ("distance planting",
     "The 96% alert precision claim was withdrawn after review. "
     + "Filler about coverage and districts. " * 4
     + "The forecaster achieves 96% alert precision in operational use."),
    ("subordinate clause",
     "Although an earlier estimate was corrected, the forecaster achieves "
     "96% alert precision in operational use."),
    ("trailing tack-on",
     "The forecaster achieves 96% alert precision in operational use, a "
     "figure no longer disputed."),
    ("conjoined clause",
     "The dam ablation claim was withdrawn, and separately the model "
     "delivers 96% alert precision today."),
    ("no sentence punctuation",
     "an early claim was withdrawn 96% alert precision is achieved "
     "operationally 96% again"),
]


@pytest.mark.parametrize("name,planted", ATTACKS, ids=[a[0] for a in ATTACKS])
def test_the_withdrawal_exemption_resists_rephrasing(name, planted):
    """Every one of these defeated an earlier version of the rule.

    The first defeated the 400-character window; the next three defeated
    sentence scope with a single clause; the last defeated it by removing
    sentence boundaries entirely, which made the whole document one sentence.
    """
    assert _asserted(planted, "96%"), f"{name} was not caught"


def test_the_real_disclosures_are_still_exempt():
    """Strictness that flags the honest sentences just gets itself deleted."""
    text = _pdf_text("SAILAAB-synopsis.pdf")
    assert "96%" in text, "the synopsis should still disclose the retracted claim"
    assert not _asserted(text, "96%"), "a genuine disclosure was flagged as an assertion"


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

    Proximity matters: checking that the qualifiers appear anywhere in the
    document would pass with the headline on page one and its caveat on page
    five, which is not a reader's experience of the claim.
    """
    text = _pdf_text("SAILAAB-synopsis.pdf")
    if "0.249" not in text:
        pytest.skip("synopsis no longer quotes the pooled figure")
    span = 700
    start = 0
    while (i := text.find("0.249", start)) != -1:
        near = text[max(0, i - span): i + span]
        assert "0.042" in near, (
            "a pooled AP is printed without the delete-2025 figure near it"
        )
        assert "0.004" in near and "0.521" in near, (
            "a pooled AP is printed without its interval near it"
        )
        start = i + 5


def _visible_text(html: str) -> str:
    # <head> is not rendered, and Chrome prints with --no-pdf-header-footer, so
    # the <title> never reaches the PDF; a version number there would become a
    # required token and fail this gate for no reason. Hidden elements go for
    # the same reason: the function is named for what a reader actually sees.
    body = re.sub(r"(?is)<head[^>]*>.*?</head>", " ", html)
    body = re.sub(
        r'(?is)<([a-z]+)[^>]*style="[^"]*display\s*:\s*none[^"]*"[^>]*>.*?</\1>',
        " ", body,
    )
    body = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", body)
    body = re.sub(r"(?s)<[^>]+>", " ", body)
    body = (body.replace("&amp;", "&").replace("&nbsp;", " ")
                .replace("&lt;", "<").replace("&gt;", ">"))
    return re.sub(r"\s+", " ", body)


NUMERIC = re.compile(r"\d")


@pytest.mark.parametrize("html,pdf", PAIRS, ids=[p for _, p in PAIRS])
def test_every_numeric_claim_in_the_page_reached_the_pdf(html, pdf):
    """Content parity, because timestamps cannot carry this check.

    The obvious staleness test compares mtimes, and git does not preserve them:
    a fresh checkout writes every file at the same moment, so on CI that test
    can never fail. This compares what the two documents actually say. Every
    run of digits in the page's visible text must appear in the rendered PDF,
    which is precisely the drift that shipped: the HTML gained "0.042" and
    "[0.004, 0.521]" and the PDF beside it still had neither.
    """
    page = _visible_text((DOCS / html).read_text(encoding="utf-8"))
    text = _pdf_text(pdf).replace("\n", " ")
    squashed = re.sub(r"\s+", "", text)

    missing = []
    for token in sorted({t for t in re.findall(r"[\d][\d.,%–-]*[\d%]", page)}):
        if len(token) < 3 or not NUMERIC.search(token):
            continue
        if token in text or re.sub(r"\s+", "", token) in squashed:
            continue
        missing.append(token)
    assert not missing, (
        f"{pdf} is missing figures its source page states: {missing[:12]}; "
        "run python -m pipeline.render_pdfs"
    )


@pytest.mark.parametrize("html,pdf", PAIRS, ids=[p for _, p in PAIRS])
def test_pdf_is_not_stale_against_its_source(html, pdf):
    """Local-only aid: a PDF older than its source has probably drifted.

    This cannot carry the check on its own. Git does not preserve mtimes, so a
    fresh checkout writes both files at the same instant and this can never
    fail on CI. It is kept because it gives an immediate answer in a working
    tree, where editing the copy and forgetting to re-render is exactly how the
    drift happened. The real gate is the content-parity test below.
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


def _words(s: str) -> list[str]:
    return re.findall(r"[a-z]{3,}", s.lower())


@pytest.mark.parametrize("html,pdf", PAIRS, ids=[p for _, p in PAIRS])
def test_the_pdf_still_says_what_its_page_says(html, pdf):
    """Word-level parity, because numeric parity only covers half the class.

    The drift that shipped had two halves. The numbers ("0.042", "[0.004,
    0.521]") are caught structurally by the token check above. The words
    ("hindcast risk", "hindcast P") contain no digits and were caught only by
    the RETIRED denylist, which was written after the incident by naming the
    strings already known to have shipped. A future textual correction with no
    numbers in it would be caught by neither.

    A similarity floor closes that. Measured today: 0.965 for the synopsis and
    0.936 for the business plan, so 0.90 sits clear of the noise from
    hyphenation and ligatures while a rewritten paragraph drops well below it.
    """
    page = set(_words(_visible_text((DOCS / html).read_text(encoding="utf-8"))))
    doc = set(_words(_pdf_text(pdf)))
    assert page, "no readable text in the source page"
    shared = len(page & doc) / len(page)
    assert shared >= 0.90, (
        f"{pdf} shares only {shared:.1%} of its page's vocabulary; "
        f"missing e.g. {sorted(page - doc)[:12]}; run python -m pipeline.render_pdfs"
    )
