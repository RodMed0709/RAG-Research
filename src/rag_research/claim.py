"""Typed schema for claim-cards: verifiable assertions extracted from a manuscript.

Each ``Claim`` is one atomic assertion checked against a corpus of source papers, anchored
to a cached verbatim passage (``Jumper`` — reused from the code-verify path). This is the
REVIEW-pillar mirror of ``SpecCard``: same anti-hallucination machinery, different target
(prose claims instead of ML code).
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, model_validator

from .speccard import Jumper, SourceMeta, ValueSpec


class ClaimKind(str, Enum):
    NUMERIC_FACT = "numeric_fact"        # "affects 70M people"      -> deterministic compare
    CITATION = "citation_support"        # "X showed Y [cite]"       -> judge vs cited source
    METHODOLOGICAL = "methodological"    # "we used TCAV"            -> judge vs real method
    NOVELTY = "novelty"                  # "first work to..."        -> judge vs corpus (refute)
    COMPARATIVE = "comparative"          # "outperforms SOTA"        -> compare/judge vs corpus


class ClaimVerdict(str, Enum):
    HONORED = "honored"            # evidence supports the claim (with anchor)
    CONTRADICTED = "contradicted"  # evidence refutes the claim
    UNSUPPORTED = "unsupported"    # no evidence found (potential hallucination)
    AMBIGUOUS = "ambiguous"        # human queue


class Claim(BaseModel):
    claim_id: str
    text: str
    kind: ClaimKind
    value_spec: ValueSpec | None = None
    location: str | None = None          # section / paragraph in the manuscript
    evidence: list[Jumper] = []
    verdict: ClaimVerdict | None = None

    @model_validator(mode="after")
    def _check_rules(self) -> Claim:
        errs: list[str] = []
        if self.kind in (ClaimKind.NUMERIC_FACT, ClaimKind.COMPARATIVE) and self.value_spec is None:
            errs.append(f"kind {self.kind.value} requires a value_spec")
        if not self.text.strip():
            errs.append("claim text is empty")
        if errs:
            raise ValueError("; ".join(errs))
        return self


class ClaimCard(BaseModel):
    card_id: str
    manuscript_ref: str
    claims: list[Claim]
    source_meta: SourceMeta | None = None

    @model_validator(mode="after")
    def _unique_claim_ids(self) -> ClaimCard:
        ids = [c.claim_id for c in self.claims]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate claim ids: {dupes}")
        return self

    def unsupported_count(self) -> int:
        """How many claims came back UNSUPPORTED — the headline anti-hallucination signal."""
        return sum(1 for c in self.claims if c.verdict == ClaimVerdict.UNSUPPORTED)
