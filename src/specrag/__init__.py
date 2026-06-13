"""specrag — reproducibility-consistency verification for ML code, grounded in papers.

The core (spec-cards + verify) is light and dependency-injected; the PaperQA2 substrate
lives behind the ``[paperqa]`` extra.
"""
from __future__ import annotations

from .speccard import (
    Cat,
    Jumper,
    LocatorKind,
    Phase,
    SourceMeta,
    SpecCard,
    SpecField,
    State,
    ValueKind,
    ValueSpec,
    VLevel,
)
from .verify import (
    FieldVerdict,
    deterministic_compare,
    flip_rate,
    verify_consistency,
    verify_field,
)

__version__ = "0.0.1"

__all__ = [
    "Cat",
    "ValueKind",
    "LocatorKind",
    "Phase",
    "VLevel",
    "State",
    "ValueSpec",
    "Jumper",
    "SpecField",
    "SourceMeta",
    "SpecCard",
    "FieldVerdict",
    "verify_field",
    "verify_consistency",
    "flip_rate",
    "deterministic_compare",
]
