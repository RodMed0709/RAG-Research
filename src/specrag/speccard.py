"""Typed schema for spec-cards: reproducibility constraints extracted from ML papers.

Each ``SpecField`` is a typed constraint (one ``paper × method``) anchored to a cached
verbatim passage (``Jumper``). The schema is the authoritative source `speccard_schema.md`.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, model_validator


class Cat(str, Enum):
    HYPERPARAMETER = "hyperparameter"
    AUGMENTATION = "augmentation"
    AUGMENTATION_PIPELINE = "augmentation_pipeline"
    NORMALIZATION = "normalization"
    EQUATION = "equation"
    SCHEDULE = "schedule"
    SEED = "seed"
    OTHER = "other"


class ValueKind(str, Enum):
    NUMERIC = "numeric"
    ENUM = "enum"
    STRUCT = "struct"
    RANGE = "range"
    FREEFORM = "freeform"


class LocatorKind(str, Enum):
    LITERAL = "literal"
    SEMANTIC = "semantic"


class Phase(str, Enum):
    TRAIN = "train"
    EVAL = "eval"
    BOTH = "both"


class VLevel(str, Enum):
    HUMAN = "human"
    SELF = "self-consistent"
    UNVERIFIED = "unverified"


class State(str, Enum):
    HONORED = "honored"
    VIOLATED = "violated"
    MISSING = "missing"
    NOT_APPLICABLE = "not_applicable"
    AMBIGUOUS = "ambiguous"


# weakest -> strongest, for the moat-critical rollup
_LEVEL_RANK = {VLevel.UNVERIFIED: 0, VLevel.SELF: 1, VLevel.HUMAN: 2}


class ValueSpec(BaseModel):
    kind: ValueKind
    equals: object | None = None
    atol: float | None = None
    rtol: float | None = None
    aliases: list[str] | None = None
    low: float | None = None
    high: float | None = None
    inclusive: bool = True
    fields: dict[str, object] | None = None
    text: str | None = None


class Jumper(BaseModel):
    pq_dockey: str
    verbatim_text: str
    anchor_phrase: str
    page_range: str | None = None
    char_span: tuple[int, int] | None = None
    media: bytes | None = None
    media_index: int | None = None
    bbox: tuple[float, ...] | None = None


class SpecField(BaseModel):
    name: str
    category: Cat
    value_kind: ValueKind
    locator_kind: LocatorKind
    value_spec: ValueSpec
    unit: str | None = None
    compare_in: str | None = None
    phase: Phase | None = None
    applies_when: str | None = None
    moat_critical: bool = False
    not_reported: bool = False
    searched_passages: list[Jumper] | None = None
    value_in_media: bool = False
    jumper: Jumper | None = None
    verification_level: VLevel = VLevel.UNVERIFIED

    @model_validator(mode="after")
    def _check_rules(self) -> SpecField:
        if self.category in (Cat.AUGMENTATION, Cat.AUGMENTATION_PIPELINE) and self.phase is None:
            raise ValueError(f"phase is required for category {self.category.value}")
        if self.not_reported and not self.searched_passages:
            raise ValueError("not_reported=True requires a non-empty searched_passages")
        if not self.not_reported and self.jumper is None:
            raise ValueError("a reported field requires a jumper")
        if self.value_in_media and (self.jumper is None or self.jumper.media is None):
            raise ValueError("value_in_media=True requires jumper.media")
        return self


class SourceMeta(BaseModel):
    created_at: datetime
    extractor_model: str


class SpecCard(BaseModel):
    card_id: str
    paper_ref: str
    method: str
    version: int = 1
    fields: list[SpecField]
    source_meta: SourceMeta | None = None

    def verification_summary(self) -> dict[str, object]:
        """Non-blocking rollup. The real blocking decision is per-field, not per-card."""
        counts = {VLevel.HUMAN: 0, VLevel.SELF: 0, VLevel.UNVERIFIED: 0}
        moat_levels: list[VLevel] = []
        for f in self.fields:
            counts[f.verification_level] += 1
            if f.moat_critical:
                moat_levels.append(f.verification_level)
        weakest = min(moat_levels, key=lambda lv: _LEVEL_RANK[lv]) if moat_levels else None
        return {
            "human": counts[VLevel.HUMAN],
            "self": counts[VLevel.SELF],
            "unverified": counts[VLevel.UNVERIFIED],
            "min_moat_critical": weakest.value if weakest is not None else None,
        }
