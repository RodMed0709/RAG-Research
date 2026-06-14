"""Integration test: the full seam chain composes with deterministic fakes (no paperqa, no LLM).

Per-module unit tests pass over the seams (review G6). This exercises them together:
Passage -> extract_field -> make_jumper -> build_field -> SpecCard -> verify_consistency ->
generate_and_verify -> check_stamp. If a type stops lining up between modules, this breaks.
"""
import re

from rag_research import (
    Cat,
    LocatorKind,
    SpecCard,
    State,
    ValueKind,
    build_field,
    check_stamp,
    generate_and_verify,
    verify_consistency,
)
from rag_research.extract import extract_field
from rag_research.substrate import Passage, make_jumper


def locate_batch(field, code):
    m = re.search(r"batch_size\s*=\s*(\d+)", code)
    return m.group(1) if m else None


def judge_noop(field, code):
    return State.AMBIGUOUS


def test_full_pipeline_composes_end_to_end():
    # 1. substrate: a retrieved passage with cached verbatim
    passage = Passage(
        pq_dockey="d", verbatim_text="trained with a batch size of 8 per GPU",
        page_range="pages 5-6", doc_citation="cite",
    )

    # 2. extract: two distinct fakes agree -> self-consistent
    out = extract_field(
        passage, "batch_size",
        extractor=lambda t, f: "8", reader=lambda t, f: "8",
        extractor_id="A", reader_id="B",
    )
    assert out.value == "8"
    assert out.independent_readback is True

    # 3. make_jumper bridges passage + value -> self-sufficient jumper
    jumper = make_jumper(passage, out.value)
    assert jumper is not None

    # 4. build: typed SpecField from the extracted STRING value (the F1 bridge)
    field = build_field(
        "batch_size", out.value, value_kind=ValueKind.NUMERIC, locator_kind=LocatorKind.LITERAL,
        category=Cat.HYPERPARAMETER, jumper=jumper, verification_level=out.verification_level,
        moat_critical=True,
    )
    assert field.value_spec.equals == 8

    # 5. card -> verify honoring code -> HONORED
    card = SpecCard(card_id="p::m", paper_ref="p", method="m", fields=[field])
    verdicts = verify_consistency(card, "batch_size = 8", locate=locate_batch, judge=judge_noop)
    assert verdicts[0].state == State.HONORED

    # 6. generate + verify + stamp bundles
    result = generate_and_verify(card, generator=lambda c: "batch_size = 8",
                                 locate=locate_batch, judge=judge_noop)
    assert result.blocked is False
    assert result.stamp.card_version == 1

    # 7. re-extraction changes the value -> old stamp goes STALE
    field2 = build_field(
        "batch_size", "16", value_kind=ValueKind.NUMERIC, locator_kind=LocatorKind.LITERAL,
        category=Cat.HYPERPARAMETER, jumper=jumper, moat_critical=True,
    )
    card2 = SpecCard(card_id="p::m", paper_ref="p", method="m", version=2, fields=[field2])
    report = check_stamp(result.stamp, card2)
    assert report.stale is True
    assert "batch_size" in report.changed_fields


def test_full_pipeline_blocks_violation_end_to_end():
    passage = Passage(pq_dockey="d", verbatim_text="batch size of 8", page_range="p", doc_citation="c")
    out = extract_field(passage, "batch_size", extractor=lambda t, f: "8", reader=lambda t, f: "8",
                        extractor_id="A", reader_id="B")
    field = build_field("batch_size", out.value, value_kind=ValueKind.NUMERIC,
                        locator_kind=LocatorKind.LITERAL, category=Cat.HYPERPARAMETER,
                        jumper=make_jumper(passage, "8"))
    card = SpecCard(card_id="p::m", paper_ref="p", method="m", fields=[field])
    result = generate_and_verify(card, generator=lambda c: "batch_size = 16",
                                 locate=locate_batch, judge=judge_noop)
    assert result.blocked is True
    assert result.stamp.generated_blocked is True
