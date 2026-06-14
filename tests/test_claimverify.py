"""Claim verify engine, exercised with injected fakes — no network, no PaperQA2."""
from rag_research.claim import Claim, ClaimCard, ClaimKind, ClaimVerdict
from rag_research.claimverify import _compare_value_spec, verify_claim, verify_claimcard
from rag_research.speccard import State, ValueKind, ValueSpec
from rag_research.substrate import Passage


def _passage(text: str = "the disease affects 70000000 people worldwide") -> Passage:
    return Passage(pq_dockey="d1", verbatim_text=text, page_range="pages 1-2", doc_citation="Doe 2020")


def _retriever(passages):
    return lambda _q, _k: list(passages)


def _judge(verdict):
    return lambda _t, _p: verdict


def _extractor(value):
    return lambda _t, _p: value


# --- anti-hallucination invariants -------------------------------------------------

def test_no_passages_is_unsupported():
    c = Claim(claim_id="c", text="x", kind=ClaimKind.METHODOLOGICAL)
    verify_claim(
        c, retrieve=_retriever([]), judge=_judge(ClaimVerdict.HONORED), extractor=_extractor("1")
    )
    assert c.verdict == ClaimVerdict.UNSUPPORTED
    assert c.evidence == []


def test_freeform_honored_carries_anchor():
    c = Claim(claim_id="c", text="we used TCAV", kind=ClaimKind.METHODOLOGICAL)
    verify_claim(
        c, retrieve=_retriever([_passage("they use TCAV with CAVs")]),
        judge=_judge(ClaimVerdict.HONORED), extractor=_extractor(None),
    )
    assert c.verdict == ClaimVerdict.HONORED
    assert len(c.evidence) == 1
    assert c.evidence[0].page_range == "pages 1-2"


def test_freeform_contradicted_passes_through():
    c = Claim(claim_id="c", text="first to use TCAV", kind=ClaimKind.NOVELTY)
    verify_claim(
        c, retrieve=_retriever([_passage()]),
        judge=_judge(ClaimVerdict.CONTRADICTED), extractor=_extractor(None),
    )
    assert c.verdict == ClaimVerdict.CONTRADICTED


# --- numeric path (deterministic) --------------------------------------------------

def test_numeric_honored():
    c = Claim(
        claim_id="c", text="affects 70M", kind=ClaimKind.NUMERIC_FACT,
        value_spec=ValueSpec(kind=ValueKind.NUMERIC, equals=70_000_000),
    )
    verify_claim(
        c, retrieve=_retriever([_passage()]),
        judge=_judge(ClaimVerdict.AMBIGUOUS), extractor=_extractor("70000000"),
    )
    assert c.verdict == ClaimVerdict.HONORED


def test_numeric_contradicted():
    c = Claim(
        claim_id="c", text="affects 70M", kind=ClaimKind.NUMERIC_FACT,
        value_spec=ValueSpec(kind=ValueKind.NUMERIC, equals=70_000_000),
    )
    verify_claim(
        c, retrieve=_retriever([_passage()]),
        judge=_judge(ClaimVerdict.AMBIGUOUS), extractor=_extractor("3000000"),
    )
    assert c.verdict == ClaimVerdict.CONTRADICTED


def test_numeric_value_not_found_is_unsupported():
    c = Claim(
        claim_id="c", text="affects 70M", kind=ClaimKind.NUMERIC_FACT,
        value_spec=ValueSpec(kind=ValueKind.NUMERIC, equals=70_000_000),
    )
    verify_claim(
        c, retrieve=_retriever([_passage()]),
        judge=_judge(ClaimVerdict.HONORED), extractor=_extractor(None),
    )
    assert c.verdict == ClaimVerdict.UNSUPPORTED


# --- regression: ENUM must not be coerced to float --------------------------------

def test_enum_compare_non_numeric():
    spec = ValueSpec(kind=ValueKind.ENUM, equals="z-score", aliases=["zero mean unit variance"])
    assert _compare_value_spec(spec, "zero mean unit variance") == State.HONORED
    assert _compare_value_spec(spec, "min-max") == State.VIOLATED


def test_range_compare():
    spec = ValueSpec(kind=ValueKind.RANGE, low=0.0, high=1.0)
    assert _compare_value_spec(spec, "0.5") == State.HONORED
    assert _compare_value_spec(spec, "2.0") == State.VIOLATED


def test_verify_claimcard_maps_all():
    a = Claim(claim_id="a", text="we used TCAV", kind=ClaimKind.METHODOLOGICAL)
    b = Claim(claim_id="b", text="novel", kind=ClaimKind.NOVELTY)
    card = ClaimCard(card_id="card", manuscript_ref="ms", claims=[a, b])
    out = verify_claimcard(
        card, retrieve=_retriever([_passage()]),
        judge=_judge(ClaimVerdict.HONORED), extractor=_extractor(None),
    )
    assert len(out) == 2
    assert all(c.verdict == ClaimVerdict.HONORED for c in out)
