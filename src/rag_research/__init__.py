"""rag_research — reproducibility-consistency verification for ML code, grounded in papers.

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
from .codegen import (
    GenerationResult,
    Stamp,
    StaleReport,
    check_stamp,
    generate_and_verify,
    make_stamp,
)
from .build import build_field, build_value_spec
from .claim import Claim, ClaimCard, ClaimKind, ClaimVerdict
from .claimverify import verify_claim, verify_claimcard

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
    "Stamp",
    "StaleReport",
    "GenerationResult",
    "make_stamp",
    "check_stamp",
    "generate_and_verify",
    "build_value_spec",
    "build_field",
    "Claim",
    "ClaimCard",
    "ClaimKind",
    "ClaimVerdict",
    "verify_claim",
    "verify_claimcard",
]
