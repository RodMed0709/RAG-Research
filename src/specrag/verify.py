"""The 2-tier verify engine.

HARD fields (``locator_kind == LITERAL`` and ``value_kind != FREEFORM``) are compared
DETERMINISTICALLY by code — the injected ``locate`` callable does any normalization
upstream, code does the comparison, the LLM never touches the verdict. SEMANTIC / FREEFORM
fields are judged by the injected ``judge`` callable (the LLM in production). This split is
what makes "consistency" honest: hard verdicts don't flip between runs.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Callable

from pydantic import BaseModel

from .speccard import Jumper, LocatorKind, SpecCard, SpecField, State, ValueKind


class FieldVerdict(BaseModel):
    field_name: str
    state: State
    blocked: bool
    verdict_source: str
    code_evidence: str | None = None
    jumper: Jumper | None = None
    localization_confidence: float | None = None
    human_override: object | None = None


Locator = Callable[[SpecField, str], "str | None"]
Judge = Callable[[SpecField, str], State]


def deterministic_compare(field: SpecField, located: str) -> State:
    """Compare a located value against the field's typed ValueSpec. Code, not LLM."""
    vs = field.value_spec

    if vs.kind == ValueKind.NUMERIC:
        if vs.equals is None:
            return State.AMBIGUOUS
        try:
            val = float(located)
            target = float(vs.equals)  # type: ignore[arg-type]
        except (ValueError, TypeError):
            return State.AMBIGUOUS
        atol = vs.atol or 0.0
        rtol = vs.rtol or 0.0
        if atol == 0.0 and rtol == 0.0:
            honored = val == target
        else:
            honored = math.isclose(val, target, rel_tol=rtol, abs_tol=atol)
        return State.HONORED if honored else State.VIOLATED

    if vs.kind == ValueKind.ENUM:
        loc = located.strip().lower()
        candidates = [vs.equals, *(vs.aliases or [])]
        for c in candidates:
            if c is not None and loc == str(c).strip().lower():
                return State.HONORED
        return State.VIOLATED

    if vs.kind == ValueKind.RANGE:
        if vs.low is None or vs.high is None:
            return State.AMBIGUOUS
        try:
            val = float(located)
        except (ValueError, TypeError):
            return State.AMBIGUOUS
        ok = vs.low <= val <= vs.high if vs.inclusive else vs.low < val < vs.high
        return State.HONORED if ok else State.VIOLATED

    # STRUCT / FREEFORM must not be compared deterministically.
    return State.AMBIGUOUS


def verify_field(field: SpecField, code: str, *, locate: Locator, judge: Judge) -> FieldVerdict:
    if field.not_reported:
        located = locate(field, code)
        state = State.MISSING if located is None else State.AMBIGUOUS
        return FieldVerdict(
            field_name=field.name, state=state, blocked=False,
            verdict_source="deterministic", jumper=field.jumper,
        )

    located = locate(field, code)
    if located is None:
        return FieldVerdict(
            field_name=field.name, state=State.MISSING, blocked=False,
            verdict_source="deterministic", jumper=field.jumper,
        )

    is_semantic = field.locator_kind == LocatorKind.SEMANTIC or field.value_kind == ValueKind.FREEFORM
    if is_semantic:
        state = judge(field, code)
        source = "llm"
    else:
        state = deterministic_compare(field, located)
        source = "deterministic"

    return FieldVerdict(
        field_name=field.name, state=state, blocked=(state == State.VIOLATED),
        verdict_source=source, jumper=field.jumper, code_evidence=located,
    )


def verify_consistency(card: SpecCard, code: str, *, locate: Locator, judge: Judge) -> list[FieldVerdict]:
    return [verify_field(f, code, locate=locate, judge=judge) for f in card.fields]


def flip_rate(
    card: SpecCard, code: str, *, locate: Locator, judge: Judge, k: int = 5
) -> dict[str, float]:
    """Run the verify k times per field; report the fraction of runs whose verdict differs
    from the modal verdict. Deterministic (literal) fields yield 0.0 — that is the point."""
    result: dict[str, float] = {}
    for field in card.fields:
        states = [verify_field(field, code, locate=locate, judge=judge).state for _ in range(k)]
        modal = Counter(states).most_common(1)[0][0]
        result[field.name] = sum(1 for s in states if s != modal) / k
    return result
