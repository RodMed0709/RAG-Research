"""Contract tests for codegen + version stamp (Phase 4, schema §5).

The version stamp is the anti-inconsistency mechanism (dolor #1): generated code records
which card version it was validated against; if the card is re-extracted and a value
changes, previously generated code is flagged STALE instead of drifting silently. The code
generator is an INJECTED callable (the LLM), so these run deterministically with fakes.
"""
from specrag import Cat, LocatorKind, SpecCard, SpecField, State, ValueKind, ValueSpec
from specrag.codegen import (
    GenerationResult,
    Stamp,
    StaleReport,
    check_stamp,
    generate_and_verify,
    make_stamp,
)
from specrag.speccard import Jumper


def _jumper() -> Jumper:
    return Jumper(pq_dockey="d", verbatim_text="batch size of 8", anchor_phrase="batch size of 8")


def _card(version: int = 1, batch: int = 8) -> SpecCard:
    return SpecCard(
        card_id="p::m", paper_ref="p", method="m", version=version,
        fields=[
            SpecField(
                name="batch_size", category=Cat.HYPERPARAMETER,
                value_kind=ValueKind.NUMERIC, locator_kind=LocatorKind.LITERAL,
                value_spec=ValueSpec(kind=ValueKind.NUMERIC, equals=batch),
                jumper=_jumper(),
            )
        ],
    )


def locate_batch(field, code):
    import re
    m = re.search(r"batch_size\s*=\s*(\d+)", code)
    return m.group(1) if m else None


def judge_noop(field, code):
    return State.AMBIGUOUS


# --- stamp ---

def test_make_stamp_records_card_identity_and_version():
    s = make_stamp(_card(version=3))
    assert isinstance(s, Stamp)
    assert s.card_id == "p::m"
    assert s.card_version == 3
    assert "batch_size" in s.field_specs


def test_stamp_fresh_when_card_unchanged():
    card = _card(version=1)
    s = make_stamp(card)
    report = check_stamp(s, card)
    assert isinstance(report, StaleReport)
    assert report.stale is False
    assert report.changed_fields == []


def test_stamp_stale_when_value_changes_on_reextraction():
    s = make_stamp(_card(version=1, batch=8))
    # re-extracted: batch became 16, version bumped to 2
    report = check_stamp(s, _card(version=2, batch=16))
    assert report.stale is True
    assert "batch_size" in report.changed_fields


def test_stamp_stale_on_value_change_even_if_version_not_bumped():
    # defensive: value changed but version forgotten -> still detected via value diff
    s = make_stamp(_card(version=1, batch=8))
    report = check_stamp(s, _card(version=1, batch=16))
    assert report.stale is True


# --- generate + verify + stamp bundle ---

def test_generate_and_verify_bundles_code_verdicts_stamp():
    card = _card()

    def gen(c: SpecCard) -> str:
        return "batch_size = 8\n"

    result = generate_and_verify(card, generator=gen, locate=locate_batch, judge=judge_noop)
    assert isinstance(result, GenerationResult)
    assert "batch_size = 8" in result.code
    assert result.stamp.card_version == card.version
    assert len(result.verdicts) == 1
    assert result.verdicts[0].state == State.HONORED
    assert result.blocked is False


def test_generate_and_verify_surfaces_violation():
    card = _card(batch=8)

    def gen(c: SpecCard) -> str:
        return "batch_size = 16\n"  # violates the card

    result = generate_and_verify(card, generator=gen, locate=locate_batch, judge=judge_noop)
    assert result.verdicts[0].state == State.VIOLATED
    assert result.blocked is True
