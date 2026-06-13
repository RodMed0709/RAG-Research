"""Runnable slice demo — the verify contract on a REAL hand card, end-to-end.

No PaperQA2 needed (cards are self-sufficient). A toy keyword `locate` and a toy
rule-based `judge` stand in for the production LLM. Shows the 3 polarities blocking/
passing correctly + the flip-rate stability metric.

Run:  python examples/run_slice.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from specrag import SpecCard, State, flip_rate, verify_consistency

CARD = Path(__file__).parent / "cards" / "zhou2023thyroid__MedSAM-ft.json"


def toy_locate(field, code: str) -> str | None:
    """Find a literal for the field in code. Real impl = LLM-localizer."""
    if field.name == "batch_size":
        m = re.search(r"batch_size\s*=\s*(\d+)", code)
        return m.group(1) if m else None
    if field.name == "jitter":
        return "jitter" if "jitter" in code else None
    if field.name == "dropout":
        return "dropout" if "dropout" in code else None
    return None


def toy_judge(field, code: str) -> State:
    """Judge a SEMANTIC field. Real impl = LLM. Here: jitter must be at eval, not train."""
    if field.name == "jitter":
        if "jitter" in code and "eval" in code and "train" not in code:
            return State.HONORED
        return State.VIOLATED
    return State.AMBIGUOUS


SNIPPETS = {
    "VIOLATED (jitter in train — must BLOCK)":
        "batch_size = 8\naugment.jitter(intensity=0.1)  # applied in train loop\n",
    "HONORED (jitter@eval, batch ok — must PASS)":
        "batch_size = 8\nif phase == 'eval':\n    augment.jitter(intensity=0.1)\n",
    "NOT_REPORTED (no dropout — must NOT block)":
        "batch_size = 8\nmodel = Net()  # paper never reported dropout\n",
}


def main() -> None:
    card = SpecCard.model_validate(json.loads(CARD.read_text(encoding="utf-8")))
    print(f"Card: {card.card_id}  (v{card.version})  fields={len(card.fields)}")
    print(f"verification_summary: {card.verification_summary()}\n")

    for title, code in SNIPPETS.items():
        print(f"== {title} ==")
        verdicts = verify_consistency(card, code, locate=toy_locate, judge=toy_judge)
        blocked_any = False
        for v in verdicts:
            mark = "BLOCK" if v.blocked else "ok"
            blocked_any = blocked_any or v.blocked
            print(f"   [{mark:>5}] {v.field_name:<12} {v.state.value:<14} via {v.verdict_source}")
        print(f"   --> output {'BLOCKED' if blocked_any else 'allowed'}\n")

    fr = flip_rate(card, SNIPPETS["HONORED (jitter@eval, batch ok — must PASS)"],
                   locate=toy_locate, judge=toy_judge, k=10)
    print(f"flip_rate (k=10): {fr}")
    print("  hard fields -> 0.0 (deterministic); that is the consistency guarantee.")


if __name__ == "__main__":
    main()
