"""Card-builder bridge: turn extracted string values into typed ``ValueSpec`` / ``SpecField``.

The extractor yields strings; the card needs typed values with the right comparator. This
centralizes the str->type coercion so call-sites stop reinventing it (a blind ``int()`` on
"0.0001" truncates; an exact float compare without tolerance silently mis-flags). It fails
LOUD on un-parseable numerics and refuses to build a float field without a tolerance.
"""
from __future__ import annotations

from .speccard import Cat, Jumper, LocatorKind, Phase, SpecField, ValueKind, ValueSpec, VLevel


def build_value_spec(
    value: str | None,
    value_kind: ValueKind,
    *,
    aliases: list[str] | None = None,
    atol: float | None = None,
    rtol: float | None = None,
    low: float | None = None,
    high: float | None = None,
) -> ValueSpec:
    if value_kind == ValueKind.NUMERIC:
        if value is None:
            raise ValueError("numeric field requires a value, got None")
        looks_float = "." in value or "e" in value.lower()
        if looks_float or atol is not None or rtol is not None:
            try:
                num = float(value)
            except ValueError as e:
                raise ValueError(f"cannot parse numeric value {value!r}") from e
            if atol is None and rtol is None:
                raise ValueError(
                    f"float value {value!r} requires atol or rtol (no silent exact float compare)"
                )
            return ValueSpec(kind=ValueKind.NUMERIC, equals=num, atol=atol, rtol=rtol)
        try:
            return ValueSpec(kind=ValueKind.NUMERIC, equals=int(value))
        except ValueError as e:
            raise ValueError(f"cannot parse integer value {value!r}") from e

    if value_kind == ValueKind.ENUM:
        if value is None:
            raise ValueError("enum field requires a value, got None")
        return ValueSpec(kind=ValueKind.ENUM, equals=value, aliases=aliases)

    if value_kind == ValueKind.RANGE:
        if low is None or high is None:
            raise ValueError("range field requires both low and high")
        return ValueSpec(kind=ValueKind.RANGE, low=low, high=high)

    if value_kind == ValueKind.FREEFORM:
        return ValueSpec(kind=ValueKind.FREEFORM, text=value)

    raise ValueError(f"unsupported value_kind: {value_kind}")


def build_field(
    name: str,
    value: str | None,
    *,
    value_kind: ValueKind,
    locator_kind: LocatorKind,
    category: Cat,
    jumper: Jumper,
    verification_level: VLevel = VLevel.UNVERIFIED,
    phase: Phase | None = None,
    moat_critical: bool = False,
    unit: str | None = None,
    compare_in: str | None = None,
    aliases: list[str] | None = None,
    atol: float | None = None,
    rtol: float | None = None,
    low: float | None = None,
    high: float | None = None,
) -> SpecField:
    """Assemble a typed ``SpecField`` from an extracted string value. Runs through
    ``build_value_spec`` (loud on bad numerics) and the ``SpecField`` validators (so an
    augmentation still requires a phase, etc.)."""
    value_spec = build_value_spec(
        value, value_kind, aliases=aliases, atol=atol, rtol=rtol, low=low, high=high
    )
    return SpecField(
        name=name,
        category=category,
        value_kind=value_kind,
        locator_kind=locator_kind,
        value_spec=value_spec,
        jumper=jumper,
        verification_level=verification_level,
        phase=phase,
        moat_critical=moat_critical,
        unit=unit,
        compare_in=compare_in,
    )
