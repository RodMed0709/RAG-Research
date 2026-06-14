"""Contract tests for extraction + card-vs-reality validation (Phase 3).

The extractor and the read-back reader are INJECTED callables (the LLMs in production),
so these run deterministically with fakes. Encodes schema §4: N-way agreement (N=2, +1 on
disagree), read-back from the isolated verbatim with a DIFFERENT reader, and the rule that
`self-consistent` is the CEILING the auto-checks can reach — never `human`.
"""
import pytest

from specrag import VLevel
from specrag.extract import ExtractOutcome, extract_field, nway
from specrag.substrate import Passage


def _passage(text: str = "trained with a batch size of 8 per GPU") -> Passage:
    return Passage(pq_dockey="d1", verbatim_text=text, page_range="pages 5-6", doc_citation="cite")


def seq_extractor(*values):
    """A fake extractor returning the given values in order across calls."""
    state = {"i": 0}

    def _ex(passage_text, field_name):
        i = state["i"]
        state["i"] += 1
        return values[i] if i < len(values) else values[-1]

    return _ex


def const(value):
    def _f(a, b):
        return value
    return _f


# --- N-way agreement ---

def test_nway_agreed():
    value, agreement, runs = nway(const("8"), "txt", "batch_size", n=2)
    assert value == "8"
    assert agreement == "agreed"
    assert runs == 2


def test_nway_disagree_resolved_by_majority():
    # 8, 16, 8 -> not unanimous in first 2 -> third run -> majority "8"
    value, agreement, runs = nway(seq_extractor("8", "16", "8"), "txt", "batch_size", n=2)
    assert agreement == "disagreed"
    assert runs == 3
    assert value == "8"


def test_nway_disagree_no_majority_returns_none():
    value, agreement, runs = nway(seq_extractor("8", "16", "32"), "txt", "batch_size", n=2)
    assert agreement == "disagreed"
    assert value is None


def test_nway_rejects_n_below_2():
    with pytest.raises(ValueError):
        nway(const("8"), "txt", "batch_size", n=1)
    with pytest.raises(ValueError):
        nway(const("8"), "txt", "batch_size", n=0)


# --- extract_field: N-way + read-back -> verification_level ---

def test_extract_self_consistent_when_agreed_and_readback_ok():
    out = extract_field(_passage(), "batch_size", extractor=const("8"), reader=const("8"),
                        extractor_id="ex-model", reader_id="rb-model")
    assert isinstance(out, ExtractOutcome)
    assert out.value == "8"
    assert out.readback_ok is True
    assert out.independent_readback is True
    assert out.verification_level == VLevel.SELF  # best the auto-checks reach; never HUMAN


def test_extract_flags_unverified_on_disagree():
    out = extract_field(_passage(), "batch_size",
                        extractor=seq_extractor("8", "16", "32"), reader=const("8"),
                        extractor_id="ex-model", reader_id="rb-model")
    assert out.value is None or out.agreement == "disagreed"
    assert out.verification_level == VLevel.UNVERIFIED


def test_extract_flags_unverified_on_readback_mismatch():
    # extractor agrees on 8, but the independent reader reads 32 from the verbatim -> flag
    out = extract_field(_passage(), "batch_size", extractor=const("8"), reader=const("32"),
                        extractor_id="ex-model", reader_id="rb-model")
    assert out.readback_ok is False
    assert out.verification_level == VLevel.UNVERIFIED


def test_extract_none_when_absent():
    out = extract_field(_passage("no number here"), "batch_size",
                        extractor=const(None), reader=const(None),
                        extractor_id="ex-model", reader_id="rb-model")
    assert out.value is None
    assert out.verification_level == VLevel.UNVERIFIED


def test_same_model_readback_never_self_consistent():
    # extractor and reader are the SAME model -> read-back not independent -> can't reach SELF,
    # even though the values trivially match (this is the FATAL-1 hole the gate now closes).
    out = extract_field(_passage(), "batch_size", extractor=const("8"), reader=const("8"),
                        extractor_id="same-model", reader_id="same-model")
    assert out.value == "8"
    assert out.readback_ok is True
    assert out.independent_readback is False
    assert out.verification_level == VLevel.UNVERIFIED


def test_readback_numeric_normalization_matches():
    # "8" vs "8.0" must match numerically (no false flag from lexical compare)
    out = extract_field(_passage(), "batch_size", extractor=const("8"), reader=const("8.0"),
                        extractor_id="ex-model", reader_id="rb-model")
    assert out.readback_ok is True
    assert out.verification_level == VLevel.SELF
