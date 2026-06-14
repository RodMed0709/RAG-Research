"""Runnable demo of the version stamp — the dolor #1 killer (inconsistency between sessions).

Session 1: generate code against card v1, stamp it.
Session 2: the card is re-extracted; a value changed -> bump to v2.
            check_stamp flags the old code STALE instead of letting it drift silently.

Run:  python examples/run_stamp.py
"""
from __future__ import annotations

from specrag import (
    Cat,
    LocatorKind,
    SpecCard,
    SpecField,
    State,
    ValueKind,
    ValueSpec,
    check_stamp,
    generate_and_verify,
)
from specrag.speccard import Jumper


def card(version: int, batch: int) -> SpecCard:
    return SpecCard(
        card_id="zhou2023thyroid::MedSAM-ft", paper_ref="zhou2023thyroid", method="MedSAM-ft",
        version=version,
        fields=[SpecField(
            name="batch_size", category=Cat.HYPERPARAMETER,
            value_kind=ValueKind.NUMERIC, locator_kind=LocatorKind.LITERAL,
            value_spec=ValueSpec(kind=ValueKind.NUMERIC, equals=batch), moat_critical=True,
            jumper=Jumper(pq_dockey="d", verbatim_text=f"batch size of {batch}", anchor_phrase=f"batch size of {batch}"),
        )],
    )


def locate(field, code):
    import re
    m = re.search(r"batch_size\s*=\s*(\d+)", code)
    return m.group(1) if m else None


def main() -> None:
    # SESSION 1: generate against card v1 (batch=8), stamp it
    v1 = card(version=1, batch=8)
    result = generate_and_verify(v1, generator=lambda c: "batch_size = 8\n",
                                 locate=locate, judge=lambda f, c: State.AMBIGUOUS)
    print("SESSION 1 — generated & stamped:")
    print(f"  code: {result.code.strip()!r}")
    print(f"  verdict: {result.verdicts[0].state.value}  blocked={result.blocked}")
    print(f"  stamp: card {result.stamp.card_id} v{result.stamp.card_version}\n")

    # SESSION 2: card re-extracted, batch corrected to 16 -> v2
    v2 = card(version=2, batch=16)
    report = check_stamp(result.stamp, v2)
    print("SESSION 2 — card re-extracted (batch 8 -> 16, v1 -> v2). Check old code's stamp:")
    print(f"  stale: {report.stale}")
    print(f"  reason: {report.reason}")
    print(f"  changed_fields: {report.changed_fields}")
    print("\n-> old code flagged STALE, not silently inconsistent. dolor #1 closed.")


if __name__ == "__main__":
    main()
