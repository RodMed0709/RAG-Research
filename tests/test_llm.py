"""Unit tests for the PURE parsing helpers in llm.py (no network, no key).

F1/F2 (the judge failing open on a hedged reply; multi-word values truncated) shipped because
these functions had zero tests. These lock the fail-safe behavior.
"""
import os

from rag_research.llm import _clean_value, _parse_state, load_env
from rag_research.speccard import State


def test_parse_state_exact():
    assert _parse_state("HONORED") == State.HONORED
    assert _parse_state("violated") == State.VIOLATED
    assert _parse_state("HONORED.") == State.HONORED


def test_parse_state_fails_safe_on_mixed_reply():
    # a hedged reply naming two states must NOT silently pass as HONORED
    assert _parse_state("this is HONORED but actually VIOLATED") == State.AMBIGUOUS


def test_parse_state_no_substring_false_positive():
    assert _parse_state("this dishonored approach") == State.AMBIGUOUS  # 'dishonored' != HONORED


def test_parse_state_unknown_is_ambiguous():
    assert _parse_state("maybe?") == State.AMBIGUOUS


def test_clean_value_keeps_multiword():
    assert _clean_value("zero mean unit variance") == "zero mean unit variance"


def test_clean_value_strips_surrounding_punct():
    assert _clean_value("8.") == "8"
    assert _clean_value("'z-score'") == "z-score"


def test_clean_value_none():
    assert _clean_value("NONE") is None
    assert _clean_value("   ") is None


def test_load_env_strips_quotes(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('FOO_SPECRAG_TEST="bar"\n', encoding="utf-8")
    monkeypatch.delenv("FOO_SPECRAG_TEST", raising=False)
    load_env(env)
    assert os.environ["FOO_SPECRAG_TEST"] == "bar"
