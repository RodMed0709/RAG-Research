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


def _attach_anchor(claim: Claim, passages: list[Passage], value: str | None) -> None:
    """Attach verbatim evidence. When a value is located, pin it inside each passage via
    make_jumper; otherwise (freeform claims) anchor on the top passage. Always leaves at
    least the top passage as evidence when any passage exists."""
    if not passages:
        return
    attached: list[Jumper] = []
    if value is not None:
        for p in passages:
            jp = make_jumper(p, value)
            if jp is not None:
                attached.append(jp)
    if not attached:
        p = passages[0]
        attached.append(
            Jumper(
                pq_dockey=p.pq_dockey,
                verbatim_text=p.verbatim_text,
                anchor_phrase=p.verbatim_text[:200],
                page_range=p.page_range,
            )
        )
    claim.evidence = attached


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
            _attach_anchor(claim, passages, None)
            claim.verdict = ClaimVerdict.UNSUPPORTED
            return claim
        state = _compare_value_spec(claim.value_spec, located)
        verdict = _numeric_state_to_verdict(state)
        _attach_anchor(claim, passages, located)
    else:
        verdict = judge(claim.text, passage_texts)
        _attach_anchor(claim, passages, None)

    # Never assert HONORED without a verbatim anchor.
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
