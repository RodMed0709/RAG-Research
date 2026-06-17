"""State-of-the-art models and deterministic tiering for the REVIEW pillar.

The literature-search and ficha-writing happen in the agentic layer (web search is not an
MCP tool). What lives here is the *deterministic* core: a typed ficha, a novelty profile
derived from the source paper, dedup, and a rule-based tiering that is reproducible — the
same fichas always land in the same tiers. Domain is a parameter (lesion detection today, dMRI
tomorrow): nothing is hardcoded to a field.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, model_validator


class AxisRole(str, Enum):
    CORE = "core"                    # defines the paper's space (domain, task, modality)
    DIFFERENTIATOR = "differentiator"  # the rare thing the paper sells as novel
    CONTEXT = "context"             # dataset, population, region — supporting, not novel


class Tier(str, Enum):
    T1 = "T1"  # direct competitor — matches the full novelty incl. the differentiator
    T2 = "T2"  # architectural twin — matches the core space but NOT the differentiator
    T3 = "T3"  # technique anchor — matches the differentiator but not the full core space
    T4 = "T4"  # context — datasets, region, background


class Threat(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    CONTEXT = "context"


class Axis(BaseModel):
    name: str            # e.g. "domain", "modality", "xai_technique", "population"
    description: str     # e.g. "lesion detection", "MRI+CT", "concept attribution", "regional cohort"
    role: AxisRole


class NoveltyProfile(BaseModel):
    """The novelty claim of the SOURCE paper, decomposed into axes. Derived from the paper
    itself by the agent, so tiering adapts to any field."""
    paper_ref: str
    axes: list[Axis]

    @model_validator(mode="after")
    def _has_differentiator(self) -> NoveltyProfile:
        if not any(a.role == AxisRole.DIFFERENTIATOR for a in self.axes):
            raise ValueError("a novelty profile needs at least one differentiator axis")
        return self

    def axis_names(self, role: AxisRole) -> list[str]:
        return [a.name for a in self.axes if a.role == role]


class Ficha(BaseModel):
    """One literature card. Lightweight metadata + the per-axis match flags that drive
    tiering. ``axis_matches`` maps axis.name -> bool (does this paper hit that axis?), filled
    by the agent during ficha creation (the semantic judgement); tiering reads it (the rule)."""
    paper_ref: str
    title: str
    authors: list[str] = []
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    arxiv: str | None = None
    modalities: list[str] = []
    is_multimodal: bool = False
    xai_techniques: list[str] = []
    metrics: dict[str, float] = {}
    pdf_status: str = "unknown"          # local | paywall | unavailable | unknown
    pdf_path: str | None = None
    github_url: str | None = None
    axis_matches: dict[str, bool] = {}
    relation_to_paper: str | None = None
    tier: Tier | None = None
    threat: Threat | None = None


def _norm_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    d = doi.strip().lower()
    for p in ("https://doi.org/", "http://doi.org/", "doi:"):
        if d.startswith(p):
            d = d[len(p):]
    return d or None


def _title_key(f: Ficha) -> str:
    t = "".join(ch for ch in f.title.lower() if ch.isalnum())
    return f"{t}|{f.year or ''}"


def dedup_fichas(fichas: list[Ficha]) -> list[Ficha]:
    """Drop duplicates by normalized DOI first, then by (title, year). Keeps the first
    occurrence — search agents overlap, so the same paper arrives from several queries."""
    seen_doi: set[str] = set()
    seen_title: set[str] = set()
    out: list[Ficha] = []
    for f in fichas:
        doi = _norm_doi(f.doi)
        key = _title_key(f)
        if doi is not None:
            if doi in seen_doi or key in seen_title:
                continue
            seen_doi.add(doi)
        elif key in seen_title:
            continue
        # Seed the title index even for DOI'd entries, so a later DOI-less copy of the same
        # paper (same title+year) is still caught.
        seen_title.add(key)
        out.append(f)
    return out


def _frac(matched: int, total: int) -> float:
    return matched / total if total else 0.0


def tier_one(profile: NoveltyProfile, ficha: Ficha, *, core_threshold: float = 0.6) -> Ficha:
    """Assign tier + threat deterministically from the ficha's per-axis match flags.

    - T1: hits the differentiator AND enough of the core space -> direct competitor.
    - T2: hits enough of the core space but NOT the differentiator -> architectural twin.
    - T3: hits the differentiator but not enough core -> technique anchor (often unimodal).
    - T4: neither -> context / dataset / region.
    """
    core = profile.axis_names(AxisRole.CORE)
    diff = profile.axis_names(AxisRole.DIFFERENTIATOR)
    m = ficha.axis_matches
    core_hit = _frac(sum(1 for n in core if m.get(n)), len(core))
    diff_hit = any(m.get(n) for n in diff)
    enough_core = core_hit >= core_threshold

    if diff_hit and enough_core:
        ficha.tier, ficha.threat = Tier.T1, Threat.HIGH
    elif enough_core and not diff_hit:
        ficha.tier, ficha.threat = Tier.T2, Threat.MEDIUM
    elif diff_hit and not enough_core:
        ficha.tier, ficha.threat = Tier.T3, Threat.LOW
    else:
        ficha.tier, ficha.threat = Tier.T4, Threat.CONTEXT
    return ficha


def tier_papers(profile: NoveltyProfile, fichas: list[Ficha], *, core_threshold: float = 0.6) -> list[Ficha]:
    """Dedup then tier every ficha. Returns fichas sorted by importance (T1 first, then by
    number of axes hit) — the ranking the reviewer reads top-down."""
    unique = dedup_fichas(fichas)
    for f in unique:
        tier_one(profile, f, core_threshold=core_threshold)
    tier_order = {Tier.T1: 0, Tier.T2: 1, Tier.T3: 2, Tier.T4: 3, None: 4}
    return sorted(
        unique,
        key=lambda f: (tier_order[f.tier], -sum(1 for v in f.axis_matches.values() if v)),
    )
