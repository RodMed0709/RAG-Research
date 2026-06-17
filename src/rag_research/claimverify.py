"""The claim verify engine — the REVIEW-pillar mirror of ``verify.py``.

A claim is checked against passages retrieved from a corpus of source papers. NUMERIC /
COMPARATIVE claims with a ``value_spec`` are compared DETERMINISTICALLY (no flip between
runs); the rest go to an injected ``judge``. Either way, a verdict is only HONORED if it
carries a ``Jumper`` anchor — an assertion without verbatim evidence is downgraded to
UNSUPPORTED. That invariant is what makes the writer/reviewer hallucination-proof.
"""
from __future__ import annotations

import math
from typing import Callable

from .claim import Claim, ClaimCard, ClaimKind, ClaimVerdict
from .speccard import Jumper, State, ValueKind, ValueSpec
from .substrate import Passage, make_jumper

# (claim_text, passage_texts) -> verdict
ClaimJudge = Callable[[str, list[str]], ClaimVerdict]
# (claim_text, passage_texts) -> located numeric/value string, or None
ClaimExtractor = Callable[[str, list[str]], "str | None"]
# (query, k) -> passages  (a sync wrapper over Substrate.retrieve, supplied by the caller)
Retriever = Callable[[str, int], list[Passage]]


def _numeric_state_to_verdict(state: State) -> ClaimVerdict:
    if state == State.HONORED:
        return ClaimVerdict.HONORED
    if state == State.VIOLATED:
        return ClaimVerdict.CONTRADICTED
    if state == State.MISSING:
        return ClaimVerdict.UNSUPPORTED
    return ClaimVerdict.AMBIGUOUS


def _compare_value_spec(spec: ValueSpec, located: str) -> State:
    """Deterministic compare of a located value against a ValueSpec. Mirrors
    ``verify.deterministic_compare``: exact unless a tolerance is given; ENUM is a string
    match (never coerced to float); STRUCT/FREEFORM are never decided here."""
    if spec.kind == ValueKind.NUMERIC:
        if spec.equals is None:
            return State.AMBIGUOUS
        try:
            val = float(located)
            target = float(spec.equals)  # type: ignore[arg-type]
        except (ValueError, TypeError):
            return State.AMBIGUOUS
        atol = spec.atol or 0.0
        rtol = spec.rtol or 0.0
        honored = val == target if (atol == 0.0 and rtol == 0.0) else math.isclose(
            val, target, rel_tol=rtol, abs_tol=atol
        )
        return State.HONORED if honored else State.VIOLATED

    if spec.kind == ValueKind.ENUM:
        loc = located.strip().lower()
        candidates = [spec.equals, *(spec.aliases or [])]
        for c in candidates:
            if c is not None and loc == str(c).strip().lower():
                return State.HONORED
        return State.VIOLATED

    if spec.kind == ValueKind.RANGE:
        if spec.low is None or spec.high is None:
            return State.AMBIGUOUS
        try:
            val = float(located)
        except (ValueError, TypeError):
            return State.AMBIGUOUS
        ok = spec.low <= val <= spec.high if spec.inclusive else spec.low < val < spec.high
        return State.HONORED if ok else State.VIOLATED

    return State.AMBIGUOUS  # STRUCT / FREEFORM


def _value_anchors(passages: list[Passage], value: str) -> list[Jumper]:
    """Jumpers that PIN ``value`` verbatim inside a passage — proof that substantiates a
    numeric verdict. Empty if the value (e.g. a normalized "70000000") never appears as-is."""
    out: list[Jumper] = []
    for p in passages:
        jp = make_jumper(p, value)
        if jp is not None:
            out.append(jp)
    return out


def _context_anchor(passages: list[Passage]) -> list[Jumper]:
    """The top passage as context evidence — what the judge/extractor actually read. Not a
    value-precise pin; used for freeform verdicts and for 'looked here, found nothing' cases."""
    if not passages:
        return []
    p = passages[0]
    return [
        Jumper(
            pq_dockey=p.pq_dockey,
            verbatim_text=p.verbatim_text,
            anchor_phrase=p.verbatim_text[:200],
            page_range=p.page_range,
        )
    ]


def verify_claim(
    claim: Claim,
    *,
    retrieve: Retriever,
    judge: ClaimJudge,
    extractor: ClaimExtractor,
    k: int = 8,
) -> Claim:
    passages = retrieve(claim.text, k)
    if not passages:
        # Nothing in the corpus speaks to this claim: the hard anti-hallucination signal.
        claim.verdict = ClaimVerdict.UNSUPPORTED
        return claim

    passage_texts = [p.verbatim_text for p in passages]

    if claim.kind in (ClaimKind.NUMERIC_FACT, ClaimKind.COMPARATIVE) and claim.value_spec is not None:
        located = extractor(claim.text, passage_texts)
        if located is None:
            claim.evidence = _context_anchor(passages)
            claim.verdict = ClaimVerdict.UNSUPPORTED
            return claim
        verdict = _numeric_state_to_verdict(_compare_value_spec(claim.value_spec, located))
        precise = _value_anchors(passages, located)
        if precise:
            # The compared value is pinned verbatim in a passage — strongest evidence.
            claim.evidence = precise
        else:
            # Value matched per the extractor but we could NOT anchor it verbatim (e.g. the
            # source says "70 million", not "70000000"). We refuse to assert HONORED without a
            # value-precise anchor — that is the anti-hallucination guarantee — so a would-be
            # HONORED goes to the human queue. Keep context passages as what we looked at.
            claim.evidence = _context_anchor(passages)
            if verdict == ClaimVerdict.HONORED:
                verdict = ClaimVerdict.AMBIGUOUS
    else:
        verdict = judge(claim.text, passage_texts)
        claim.evidence = _context_anchor(passages)

    # Defensive: never assert HONORED without any anchor at all.
    if verdict == ClaimVerdict.HONORED and not claim.evidence:
        verdict = ClaimVerdict.UNSUPPORTED
    claim.verdict = verdict
    return claim


def verify_claimcard(
    card: ClaimCard,
    *,
    retrieve: Retriever,
    judge: ClaimJudge,
    extractor: ClaimExtractor,
    k: int = 8,
) -> list[Claim]:
    for claim in card.claims:
        verify_claim(claim, retrieve=retrieve, judge=judge, extractor=extractor, k=k)
    return card.claims
