"""Version stamp (schema §5): closes dolor #1 — inconsistency between sessions.

Generated code is stamped against the card's identity, version, AND a per-field snapshot of
every reproducibility-affecting attribute (value, phase, unit, normalization, verification
level, ...). If the card is later re-extracted and ANY of those change — including a phase
flip train->eval, the canonical jitter bug — ``check_stamp`` reports the old code STALE
instead of letting it drift silently. The generator is INJECTED (the LLM), so this is
testable with fakes. The stamp also records whether the code was blocked/flagged at
generation, so a future ``check_stamp`` can't read "fresh" as "all good".
"""
from __future__ import annotations

from typing import Callable

from pydantic import BaseModel, computed_field

from .speccard import SpecCard
from .verify import FieldVerdict, Judge, Locator, verify_consistency

Generator = Callable[[SpecCard], str]

# Everything on a SpecField except the evidence/localization (jumper, searched_passages),
# which is allowed to change on re-localization without meaning the constraint changed.
_NON_SNAPSHOT = {"jumper", "searched_passages"}


def _snapshot(card: SpecCard) -> dict[str, dict[str, object]]:
    return {f.name: f.model_dump(mode="json", exclude=_NON_SNAPSHOT) for f in card.fields}


class Stamp(BaseModel):
    card_id: str
    card_version: int
    field_specs: dict[str, dict[str, object]]
    generated_blocked: bool = False
    generated_needs_human: bool = False


class StaleReport(BaseModel):
    stale: bool
    reason: str
    changed_fields: list[str]


class GenerationResult(BaseModel):
    code: str
    verdicts: list[FieldVerdict]
    stamp: Stamp

    @computed_field  # type: ignore[prop-decorator]
    @property
    def blocked(self) -> bool:
        return any(v.blocked for v in self.verdicts)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def needs_human(self) -> bool:
        return any(v.needs_human for v in self.verdicts)


def make_stamp(card: SpecCard, *, blocked: bool = False, needs_human: bool = False) -> Stamp:
    return Stamp(
        card_id=card.card_id,
        card_version=card.version,
        field_specs=_snapshot(card),
        generated_blocked=blocked,
        generated_needs_human=needs_human,
    )


def check_stamp(stamp: Stamp, current_card: SpecCard) -> StaleReport:
    """Stale if the card id/version changed, or any field's reproducibility snapshot differs,
    including fields ADDED or REMOVED since the stamp (the union of both key sets is checked)."""
    if current_card.card_id != stamp.card_id:
        return StaleReport(
            stale=True,
            reason=f"card_id mismatch: stamped {stamp.card_id}, got {current_card.card_id}",
            changed_fields=[],
        )

    current = _snapshot(current_card)
    all_names = set(stamp.field_specs) | set(current)
    changed = sorted(n for n in all_names if current.get(n) != stamp.field_specs.get(n))
    version_changed = current_card.version != stamp.card_version
    stale = version_changed or bool(changed)

    if not stale:
        reason = f"fresh: code still matches card v{stamp.card_version}"
    else:
        parts = []
        if version_changed:
            parts.append(f"version changed: stamped v{stamp.card_version}, got v{current_card.version}")
        if changed:
            parts.append(f"changed/added/removed fields: {', '.join(changed)}")
        reason = "; ".join(parts)

    return StaleReport(stale=stale, reason=reason, changed_fields=changed)


def generate_and_verify(
    card: SpecCard, *, generator: Generator, locate: Locator, judge: Judge
) -> GenerationResult:
    """Generate code from the card (injected LLM), verify it against the same card, and stamp
    it — recording in the stamp whether the verify blocked/flagged the result, so a clean
    ``check_stamp`` later cannot be mistaken for a clean verify."""
    code = generator(card)
    verdicts = verify_consistency(card, code, locate=locate, judge=judge)
    blocked = any(v.blocked for v in verdicts)
    needs_human = any(v.needs_human for v in verdicts)
    stamp = make_stamp(card, blocked=blocked, needs_human=needs_human)
    return GenerationResult(code=code, verdicts=verdicts, stamp=stamp)
