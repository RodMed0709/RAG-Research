"""Pure-logic tests for the substrate bridge (no PaperQA2 / torch needed).

The live Substrate class (ingest/retrieve) is exercised by the smoke script against real
PDFs; here we lock the deterministic helpers.
"""
from rag_research.substrate import Passage, make_jumper, parse_page_range, slugify_ref


def test_parse_page_range_pdf():
    assert parse_page_range("camus chunk pages 5-6") == "pages 5-6"
    assert parse_page_range("doc pages 12") == "pages 12"


def test_parse_page_range_absent():
    assert parse_page_range("doc chunk 3") is None  # plain-text chunk, no page
    assert parse_page_range(None) is None
    assert parse_page_range("") is None


def test_slugify_ref():
    assert slugify_ref("Zhou et al. 2023 (Thyroid)") == "zhou-et-al-2023-thyroid"
    assert slugify_ref("!!!") == "paper"


def _passage(text: str) -> Passage:
    return Passage(pq_dockey="d1", verbatim_text=text, page_range="pages 4-4", doc_citation="cite")


def test_make_jumper_single_occurrence():
    p = _passage("We trained with a batch size of 8 per GPU for 200 epochs.")
    j = make_jumper(p, "8")
    assert j is not None
    assert j.verbatim_text == p.verbatim_text  # full verbatim cached
    assert "8" in j.anchor_phrase
    assert j.char_span is not None
    lo, hi = j.char_span
    assert j.anchor_phrase[lo:hi] == "8"  # span is within the anchor phrase, not the raw chunk


def test_make_jumper_absent_returns_none():
    p = _passage("no numeric value here")
    assert make_jumper(p, "8") is None


def test_make_jumper_homonym_leaves_span_none():
    # "8" appears twice (batch 8 and Figure 8) -> ambiguous -> char_span None (flag, don't guess)
    p = _passage("batch size of 8; see Figure 8 for details")
    j = make_jumper(p, "8")
    assert j is not None
    assert j.char_span is None
