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
from .litreview import (
    Axis,
    AxisRole,
    Ficha,
    NoveltyProfile,
    Threat,
    Tier,
    dedup_fichas,
    tier_papers,
)
from .report import render_reporte, render_v2
from .consistency import (
    Finding,
    Severity,
    confusion_matrix_check,
    detect_missing_sections,
    detect_terminology_variants,
    render_review,
)
from .references import build_bibliography, detect_missing_citations, ficha_to_bibtex
from .delivery import (
    TrackedChange,
    latex_tracked,
    render_latex_changes,
    render_tracked_changes,
)
from .draft import (
    NO_SUPPORT,
    DraftCard,
    DraftSection,
    DraftStatus,
    Writer,
    draft_bullet,
    draft_section,
    render_draft_section,
)
from .codewrite import (
    CodeClaim,
    CodeStatus,
    CodeValueLocator,
    CodeWriter,
    MethodsDraft,
    draft_code_claim,
    draft_methods,
    render_methods,
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
    "Axis",
    "AxisRole",
    "Tier",
    "Threat",
    "NoveltyProfile",
    "Ficha",
    "tier_papers",
    "dedup_fichas",
    "render_reporte",
    "render_v2",
    "Severity",
    "Finding",
    "detect_terminology_variants",
    "confusion_matrix_check",
    "detect_missing_sections",
    "render_review",
    "ficha_to_bibtex",
    "build_bibliography",
    "detect_missing_citations",
    "TrackedChange",
    "render_tracked_changes",
    "render_latex_changes",
    "latex_tracked",
    "DraftStatus",
    "Writer",
    "NO_SUPPORT",
    "DraftCard",
    "DraftSection",
    "draft_bullet",
    "draft_section",
    "render_draft_section",
    "CodeStatus",
    "CodeValueLocator",
    "CodeWriter",
    "CodeClaim",
    "MethodsDraft",
    "draft_code_claim",
    "draft_methods",
    "render_methods",
]
