import pytest

from rag_research.claim import Claim, ClaimCard, ClaimKind, ClaimVerdict
from rag_research.speccard import ValueKind, ValueSpec


def _numeric_claim(cid: str = "c1") -> Claim:
    return Claim(
        claim_id=cid,
        text="lesion detection affects 70 million people",
        kind=ClaimKind.NUMERIC_FACT,
        value_spec=ValueSpec(kind=ValueKind.NUMERIC, equals=70_000_000),
    )


def test_freeform_claim_needs_no_value_spec():
    c = Claim(claim_id="c", text="we used TCAV", kind=ClaimKind.METHODOLOGICAL)
    assert c.value_spec is None


def test_numeric_claim_requires_value_spec():
    with pytest.raises(ValueError, match="requires a value_spec"):
        Claim(claim_id="c", text="affects 70M", kind=ClaimKind.NUMERIC_FACT)


def test_comparative_claim_requires_value_spec():
    with pytest.raises(ValueError, match="requires a value_spec"):
        Claim(claim_id="c", text="beats SOTA", kind=ClaimKind.COMPARATIVE)


def test_empty_text_rejected():
    with pytest.raises(ValueError, match="empty"):
        Claim(claim_id="c", text="   ", kind=ClaimKind.NOVELTY)


def test_duplicate_claim_ids_rejected():
    with pytest.raises(ValueError, match="duplicate claim ids"):
        ClaimCard(
            card_id="card",
            manuscript_ref="ms",
            claims=[_numeric_claim("dup"), _numeric_claim("dup")],
        )


def test_unsupported_count():
    a = _numeric_claim("a")
    b = Claim(claim_id="b", text="novel approach", kind=ClaimKind.NOVELTY)
    a.verdict = ClaimVerdict.UNSUPPORTED
    b.verdict = ClaimVerdict.HONORED
    card = ClaimCard(card_id="card", manuscript_ref="ms", claims=[a, b])
    assert card.unsupported_count() == 1
