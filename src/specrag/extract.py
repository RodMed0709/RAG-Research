"""Schema §4: card-vs-reality auto-checks using injected extractor / reader callables.

The ``Extractor`` and ``ReadBack`` callables are INJECTED so the module is testable with
fakes and swappable for local/Claude models. The read-back MUST use a DIFFERENT model than
the extractor — if they share a model their errors correlate and the cross-check is worthless.
This is enforced in code, not just documented: ``extract_field`` requires an ``extractor_id``
and a ``reader_id``; if they are equal the read-back is not independent and the field can NOT
reach ``self-consistent`` (it stays ``unverified`` — a flag for a human).

These auto-checks only ever reach ``self-consistent``; ``human`` requires a person confirming
the flag (out of scope here). Their job is to shrink the human queue, not replace it. And
N-way agreement proves a model is STABLE, not CORRECT — only the independent read-back adds
real signal, which is why its independence is enforced.
"""
from __future__ import annotations

import math
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
    independent_readback: bool = False
    verification_level: VLevel


def _norm(s: str) -> str:
    return s.strip().lower()


def _anchor_window(text: str, value: str, window: int = 60) -> str:
    """Tight window around the first occurrence of ``value`` in ``text`` — so the read-back
    reads the LOCAL context, not the whole ~5000-char chunk (schema §5: read-back on the
    anchor). Falls back to the full text if the value is not literally present."""
    i = text.find(value)
    if i < 0:
        return text
    return text[max(0, i - window): i + len(value) + window]


def _values_match(a: str, b: str) -> bool:
    """Typed-ish comparison: numbers compared as numbers (so "8" == "8.0"), else lexical.
    A reader that reads "32" from "8 per GPU x 4 GPUs" must NOT match an extractor's "8"."""
    try:
        return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-9)
    except (ValueError, TypeError):
        return _norm(a) == _norm(b)


def nway(extractor: Extractor, passage_text: str, field_name: str, n: int = 2) -> tuple[str | None, str, int]:
    """N-way agreement (schema §4.1). Extract n times; unanimous & non-None -> 'agreed'.
    Otherwise extract once more and take a strict majority (count >= 2) over non-None results,
    else None. The disagreement IS the ambiguity signal. Requires n >= 2 (N-way of 1 is not
    agreement)."""
    if n < 2:
        raise ValueError("nway requires n >= 2 (N-way agreement needs at least two extractions)")
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
    extractor_id: str,
    reader_id: str,
    n: int = 2,
) -> ExtractOutcome:
    """N-way agreement + an INDEPENDENT read-back from the isolated verbatim.

    ``verification_level`` reaches ``self-consistent`` only if (a) the extractor agreed,
    (b) an independent read-back (``reader_id != extractor_id``) confirmed the value, with
    numeric-aware matching. Otherwise ``unverified`` — a flag for a human. A read-back from
    the SAME model as the extractor is not independent and never earns ``self-consistent``.
    """
    value, agreement, runs = nway(extractor, passage.verbatim_text, field_name, n)
    independent = extractor_id != reader_id

    readback_value: str | None = None
    readback_ok: bool | None = None
    if value is not None:
        # read-back reads only the local window around the value, not the whole chunk
        anchor = _anchor_window(passage.verbatim_text, value)
        readback_value = reader(anchor, field_name)
        readback_ok = readback_value is not None and _values_match(readback_value, value)

    level = (
        VLevel.SELF
        if (agreement == "agreed" and value is not None and readback_ok is True and independent)
        else VLevel.UNVERIFIED
    )
    return ExtractOutcome(
        field_name=field_name,
        value=value,
        agreement=agreement,
        n_runs=runs,
        readback_value=readback_value,
        readback_ok=readback_ok,
        independent_readback=independent,
        verification_level=level,
    )
