"""Contract tests for verify_consistency (Phase 1, Tasks 1.5-1.7).

The verify is 2-tier: HARD fields are compared deterministically (code compares;
the injected `locate` does any normalization, e.g. per-GPU); SEMANTIC / FREEFORM
fields are judged by the injected `judge` (the LLM in production). The 3 polarities
and the flip-rate metric are the slice's success criteria.
"""
from rag_research import (
    Cat,
    FieldVerdict,
    Jumper,
    LocatorKind,
    Phase,
    SpecCard,
    SpecField,
    State,
    ValueKind,
    ValueSpec,
    VLevel,
    flip_rate,
    verify_consistency,
    verify_field,
)


def _jumper(**kw) -> Jumper:
    base = dict(pq_dockey="d", verbatim_text="v", anchor_phrase="v")
    base.update(kw)
    return Jumper(**base)


def _hard(name="batch_size", value_spec=None, **kw) -> SpecField:
    return SpecField(
        name=name,
        category=Cat.HYPERPARAMETER,
        value_kind=(value_spec.kind if value_spec else ValueKind.NUMERIC),
        locator_kind=LocatorKind.LITERAL,
        value_spec=value_spec or ValueSpec(kind=ValueKind.NUMERIC, equals=8),
        jumper=_jumper(),
        **kw,
    )


def _semantic_jitter(**kw) -> SpecField:
    return SpecField(
        name="jitter",
        category=Cat.AUGMENTATION,
        value_kind=ValueKind.ENUM,
        locator_kind=LocatorKind.SEMANTIC,
        value_spec=ValueSpec(kind=ValueKind.ENUM, equals="intensity_jitter", aliases=["intensity perturbation"]),
        phase=Phase.EVAL,
        jumper=_jumper(),
        **kw,
    )


# fakes (deterministic — no RNG)
def locate_found(value):
    def _loc(field, code):
        return value
    return _loc


def locate_absent(field, code):
    return None


def judge_const(state):
    def _judge(field, code):
        return state
    return _judge


# --- Task 1.5: deterministic compare ---

def test_hard_int_honored():
    v = verify_field(_hard(), "batch_size = 8", locate=locate_found("8"), judge=judge_const(State.VIOLATED))
    assert v.state == State.HONORED
    assert v.verdict_source == "deterministic"
    assert v.blocked is False


def test_hard_int_violated():
    v = verify_field(_hard(), "batch_size = 16", locate=locate_found("16"), judge=judge_const(State.HONORED))
    assert v.state == State.VIOLATED
    assert v.blocked is True


def test_hard_int_normalized_by_locator():
    # field is per-GPU=8; global batch 32 / world_size 4 normalized to "8" UPSTREAM by the locator
    f = _hard(unit="per_gpu", compare_in="per_gpu")
    v = verify_field(f, "batch=32; world_size=4", locate=locate_found("8"), judge=judge_const(State.VIOLATED))
    assert v.state == State.HONORED


def test_hard_float_tolerance():
    f = _hard(name="lr", value_spec=ValueSpec(kind=ValueKind.NUMERIC, equals=1e-4, atol=1e-6))
    v = verify_field(f, "lr = 0.0001", locate=locate_found("0.0001"), judge=judge_const(State.VIOLATED))
    assert v.state == State.HONORED


def test_enum_alias_honored():
    f = SpecField(
        name="normalization", category=Cat.NORMALIZATION,
        value_kind=ValueKind.ENUM, locator_kind=LocatorKind.LITERAL,
        value_spec=ValueSpec(kind=ValueKind.ENUM, equals="z-score",
                             aliases=["zero mean unit variance"]),
        jumper=_jumper(),
    )
    v = verify_field(f, "...", locate=locate_found("zero mean unit variance"), judge=judge_const(State.VIOLATED))
    assert v.state == State.HONORED


# --- Task 1.6: the 3 polarities + routing ---

def test_violated_blocks():
    v = verify_field(_semantic_jitter(), "jitter in train", locate=locate_found("jitter"), judge=judge_const(State.VIOLATED))
    assert v.state == State.VIOLATED
    assert v.blocked is True
    assert v.verdict_source == "llm"


def test_honored_passes():
    v = verify_field(_semantic_jitter(), "jitter at eval", locate=locate_found("jitter"), judge=judge_const(State.HONORED))
    assert v.state == State.HONORED
    assert v.blocked is False


def test_not_reported_no_block():
    f = SpecField(
        name="dropout", category=Cat.HYPERPARAMETER,
        value_kind=ValueKind.NUMERIC, locator_kind=LocatorKind.LITERAL,
        value_spec=ValueSpec(kind=ValueKind.NUMERIC),
        not_reported=True,
        searched_passages=[_jumper(verbatim_text="weight decay 1e-4", anchor_phrase="weight decay")],
        jumper=None,
    )
    v = verify_field(f, "no dropout here", locate=locate_absent, judge=judge_const(State.VIOLATED))
    assert v.state == State.MISSING
    assert v.blocked is False


def test_routing_hard_skips_judge():
    calls = []

    def spy(field, code):
        calls.append(field.name)
        return State.VIOLATED

    verify_field(_hard(), "batch_size = 8", locate=locate_found("8"), judge=spy)
    assert calls == []  # deterministic field never calls the judge


def test_routing_semantic_calls_judge():
    calls = []

    def spy(field, code):
        calls.append(field.name)
        return State.HONORED

    verify_field(_semantic_jitter(), "jitter at eval", locate=locate_found("jitter"), judge=spy)
    assert calls == ["jitter"]


def test_verify_consistency_maps_all_fields():
    card = SpecCard(
        card_id="p::m", paper_ref="p", method="m",
        fields=[_hard(), _semantic_jitter()],
    )
    verdicts = verify_consistency(card, "batch_size = 8; jitter at eval",
                                  locate=locate_found("8"), judge=judge_const(State.HONORED))
    assert len(verdicts) == 2
    assert all(isinstance(v, FieldVerdict) for v in verdicts)


# --- Task 1.7: flip_rate ---

def test_flip_rate_literal_zero():
    card = SpecCard(card_id="p::m", paper_ref="p", method="m", fields=[_hard()])
    fr = flip_rate(card, "batch_size = 8", locate=locate_found("8"), judge=judge_const(State.VIOLATED), k=10)
    assert fr["batch_size"] == 0.0


# --- Post-adversarial gate: moat-critical escalation + AMBIGUOUS never silently passes ---

def _moat_semantic(level: VLevel) -> SpecField:
    return SpecField(
        name="jitter", category=Cat.AUGMENTATION, value_kind=ValueKind.ENUM,
        locator_kind=LocatorKind.SEMANTIC,
        value_spec=ValueSpec(kind=ValueKind.ENUM, equals="intensity_jitter"),
        phase=Phase.EVAL, moat_critical=True, verification_level=level, jumper=_jumper(),
    )


def test_moat_critical_violated_self_consistent_escalates():
    # self-consistent card, VIOLATED -> do NOT auto-block; escalate to human
    v = verify_field(_moat_semantic(VLevel.SELF), "jitter in train",
                     locate=locate_found("jitter"), judge=judge_const(State.VIOLATED))
    assert v.state == State.VIOLATED
    assert v.blocked is False
    assert v.needs_human is True


def test_moat_critical_violated_human_blocks_hard():
    # human-verified card, VIOLATED -> hard block (no escalation needed)
    v = verify_field(_moat_semantic(VLevel.HUMAN), "jitter in train",
                     locate=locate_found("jitter"), judge=judge_const(State.VIOLATED))
    assert v.blocked is True
    assert v.needs_human is False


def test_ambiguous_hard_unparseable_flags_human():
    # hard NUMERIC field, code value won't parse ("eight") -> AMBIGUOUS, queued, NOT a silent pass
    f = _hard(value_spec=ValueSpec(kind=ValueKind.NUMERIC, equals=8))
    v = verify_field(f, "batch_size = eight", locate=locate_found("eight"), judge=judge_const(State.HONORED))
    assert v.state == State.AMBIGUOUS
    assert v.blocked is False
    assert v.needs_human is True


def test_not_reported_contradicted_flags_human():
    # card says not_reported, but code reports it -> contradiction surfaced to human
    f = SpecField(
        name="dropout", category=Cat.HYPERPARAMETER, value_kind=ValueKind.NUMERIC,
        locator_kind=LocatorKind.LITERAL, value_spec=ValueSpec(kind=ValueKind.NUMERIC),
        not_reported=True,
        searched_passages=[_jumper(verbatim_text="weight decay 1e-4", anchor_phrase="weight decay")],
        jumper=None,
    )
    v = verify_field(f, "dropout = 0.5", locate=locate_found("dropout"), judge=judge_const(State.HONORED))
    assert v.state == State.AMBIGUOUS
    assert v.needs_human is True
    assert v.blocked is False


def test_flip_rate_semantic_measured():
    # judge returns VIOLATED for first 7 calls, HONORED for last 3 -> flip = 3/10
    state = {"n": 0}

    def flaky(field, code):
        i = state["n"]
        state["n"] += 1
        return State.VIOLATED if i < 7 else State.HONORED

    card = SpecCard(card_id="p::m", paper_ref="p", method="m", fields=[_semantic_jitter()])
    fr = flip_rate(card, "jitter", locate=locate_found("jitter"), judge=flaky, k=10)
    assert abs(fr["jitter"] - 0.3) < 1e-9
