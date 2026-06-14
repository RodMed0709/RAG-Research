"""Schema §4: card-vs-reality auto-checks using injected extractor / reader callables.

The ``Extractor`` and ``ReadBack`` callables are INJECTED so the module is testable with
fakes and swappable for local/Claude models. The read-back MUST use a DIFFERENT model than
the extractor — if they share a model their errors correlate and the cross-check is worthless.

These auto-checks only ever reach ``self-consistent``; ``human`` requires a person confirming
the flag (out of scope here). Their job is to shrink the human queue, not replace it.
"""
from __future__ import annotations

from collections import Counter
from typing import Callable, Protocol

from pydantic import BaseModel

from .speccard import VLevel

Extractor = Callable[[str, str], "str | None"]
ReadBack = Callable[[str, str], "str | None"]


class _HasVerbatim(Protocol):
    verbatim_text: str


class ExtractOutcome(BaseModel):
    field_name: str
    value: str | None
    agreement: str
    n_runs: int
    readback_value: str | None = None
    readback_ok: bool | None = None
    verification_level: VLevel


def _norm(s: str) -> str:
    return s.strip().lower()


def nway(extractor: Extractor, passage_text: str, field_name: str, n: int = 2) -> tuple[str | None, str, int]:
    """N-way agreement (schema §4.1). Extract n times; unanimous & non-None -> 'agreed'.
    Otherwise extract once more and take a strict majority (count >= 2) over non-None results,
    else None. The disagreement IS the ambiguity signal."""
    results: list[str | None] = [extractor(passage_text, field_name) for _ in range(n)]

    first = results[0]
    if first is not None and all(r == first for r in results):
        return first, "agreed", n

    results.append(extractor(passage_text, field_name))
    non_none = [r for r in results if r is not None]
    if not non_none:
        return None, "disagreed", n + 1
    ranked = Counter(non_none).most_common()
    top_count = ranked[0][1]
    winners = [v for v, c in ranked if c == top_count]
    if len(winners) == 1 and top_count >= 2:
        return winners[0], "disagreed", n + 1
    return None, "disagreed", n + 1


def extract_field(
    passage: _HasVerbatim,
    field_name: str,
    *,
    extractor: Extractor,
    reader: ReadBack,
    n: int = 2,
) -> ExtractOutcome:
    """N-way agreement + read-back from the isolated verbatim. The resulting
    ``verification_level`` is ``self-consistent`` only if the extractor agreed AND an
    independent read-back confirmed the value; otherwise ``unverified`` (a flag for a human)."""
    value, agreement, runs = nway(extractor, passage.verbatim_text, field_name, n)

    readback_value: str | None = None
    readback_ok: bool | None = None
    if value is not None:
        readback_value = reader(passage.verbatim_text, field_name)
        readback_ok = readback_value is not None and _norm(readback_value) == _norm(value)

    level = (
        VLevel.SELF
        if (agreement == "agreed" and value is not None and readback_ok is True)
        else VLevel.UNVERIFIED
    )
    return ExtractOutcome(
        field_name=field_name,
        value=value,
        agreement=agreement,
        n_runs=runs,
        readback_value=readback_value,
        readback_ok=readback_ok,
        verification_level=level,
    )
