"""Version stamp (schema §5): closes dolor #1 — inconsistency between sessions.

Generated code is stamped against ``{card_id, version, per-field value snapshot}``. If the
card is later re-extracted and a value changes, ``check_stamp`` reports the previously
generated code STALE instead of letting it drift silently. The code generator is an INJECTED
callable (the LLM), so this is testable with fakes and swappable for a local/Claude model.
"""
from __future__ import annotations

from typing import Callable

from pydantic import BaseModel, computed_field

from .speccard import SpecCard
from .verify import FieldVerdict, Judge, Locator, verify_consistency

Generator = Callable[[SpecCard], str]


class Stamp(BaseModel):
    card_id: str
    card_version: int
    field_specs: dict[str, dict[str, object]]


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


def make_stamp(card: SpecCard) -> Stamp:
    field_specs = {f.name: f.value_spec.model_dump(mode="json") for f in card.fields}
    return Stamp(card_id=card.card_id, card_version=card.version, field_specs=field_specs)


def check_stamp(stamp: Stamp, current_card: SpecCard) -> StaleReport:
    """Compare generated-code's stamp against the current card. Stale if the card version
    changed or any stamped field's value snapshot differs (re-extraction drift)."""
    if current_card.card_id != stamp.card_id:
        return StaleReport(
            stale=True,
            reason=f"card_id mismatch: stamped {stamp.card_id}, got {current_card.card_id}",
            changed_fields=[],
        )

    current = {f.name: f.value_spec.model_dump(mode="json") for f in current_card.fields}
    changed = [name for name, spec in stamp.field_specs.items() if current.get(name) != spec]
    version_changed = current_card.version != stamp.card_version
    stale = version_changed or len(changed) > 0

    if not stale:
        reason = f"fresh: code still matches card v{stamp.card_version}"
    else:
        parts = []
        if version_changed:
            parts.append(f"version changed: stamped v{stamp.card_version}, got v{current_card.version}")
        if changed:
            parts.append(f"changed fields: {', '.join(sorted(changed))}")
        reason = "; ".join(parts)

    return StaleReport(stale=stale, reason=reason, changed_fields=changed)


def generate_and_verify(
    card: SpecCard, *, generator: Generator, locate: Locator, judge: Judge
) -> GenerationResult:
    """Generate code from the card (injected LLM), immediately verify it against the same
    card, and stamp it. The result bundles code + per-field verdicts + version stamp."""
    code = generator(card)
    verdicts = verify_consistency(card, code, locate=locate, judge=judge)
    return GenerationResult(code=code, verdicts=verdicts, stamp=make_stamp(card))
