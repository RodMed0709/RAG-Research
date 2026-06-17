"""Contract tests for WRITE-from-code (codewrite.py). The anchor is DETERMINISTIC: a Methods
sentence is written only if the located value is pinned verbatim in a code line."""
from __future__ import annotations

from rag_research.codewrite import (
    CodeStatus,
    draft_code_claim,
    draft_methods,
    render_methods,
)

CODE = """
model = MedSAM()
optimizer = Adam(model.parameters(), lr=1e-4)
train_loader = DataLoader(ds, batch_size=8, shuffle=True)
"""


def _locate_map(mapping):
    return lambda aspect, code: mapping.get(aspect)


def _write_template(aspect, value, code_line):
    return f"We set {aspect} to {value}."


# ---- value present in code -> ANCHORED with a verbatim line + lineno ----
def test_anchored_when_value_in_code():
    card = draft_code_claim(
        "batch_size", CODE,
        locate=_locate_map({"batch_size": "8"}),
        write=_write_template,
    )
    assert card.status == CodeStatus.ANCHORED
    assert card.value == "8"
    assert "batch_size=8" in card.code_line
    assert card.lineno is not None
    assert card.claim_text == "We set batch_size to 8."


# ---- locator returns nothing -> NO_EVIDENCE, no sentence ----
def test_no_evidence_when_locator_empty():
    card = draft_code_claim(
        "weight_decay", CODE,
        locate=_locate_map({}),
        write=_write_template,
    )
    assert card.status == CodeStatus.NO_EVIDENCE
    assert card.claim_text == ""


# ---- locator hallucinates a value NOT in the code -> refused (NO_EVIDENCE) ----
def test_unpinnable_value_refused():
    card = draft_code_claim(
        "batch_size", CODE,
        locate=_locate_map({"batch_size": "256"}),  # 256 is nowhere in CODE
        write=_write_template,
    )
    assert card.status == CodeStatus.NO_EVIDENCE
    assert card.value == "256"          # we keep what the locator claimed
    assert card.code_line is None       # ...but refuse to anchor it


def test_prefers_line_mentioning_aspect():
    # "8" also substring-matches "0.8" on the lr line; the anchor must land on the batch line.
    code = "lr = 0.8\nbatch_size = 8\n"
    card = draft_code_claim(
        "batch_size", code,
        locate=_locate_map({"batch_size": "8"}),
        write=_write_template,
    )
    assert card.status == CodeStatus.ANCHORED
    assert "batch_size" in card.code_line
    assert card.lineno == 2


def test_methods_counts_and_render():
    draft = draft_methods(
        ["batch_size", "lr", "weight_decay"], CODE,
        locate=_locate_map({"batch_size": "8", "lr": "1e-4"}),
        write=_write_template,
    )
    assert len(draft.claims) == 3
    assert draft.no_evidence_count() == 1
    assert len(draft.anchored()) == 2

    md = render_methods(draft, title="Implementation")
    assert "# Implementation" in md
    assert "SIN EVIDENCIA EN CÓDIGO: weight_decay" in md   # visible
    assert "Trazabilidad" in md
    assert "Sin evidencia en código: 1 de 3 aspectos." in md
    assert "`8`" in md and "`1e-4`" in md
