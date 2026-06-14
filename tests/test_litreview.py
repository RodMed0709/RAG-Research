import pytest

from rag_research.litreview import (
    Axis,
    AxisRole,
    Ficha,
    NoveltyProfile,
    Threat,
    Tier,
    dedup_fichas,
    tier_papers,
)


def _profile() -> NoveltyProfile:
    return NoveltyProfile(
        paper_ref="demo2025",
        axes=[
            Axis(name="domain", description="lesion detection", role=AxisRole.CORE),
            Axis(name="modality", description="MRI+CT", role=AxisRole.CORE),
            Axis(name="xai", description="concept attribution", role=AxisRole.DIFFERENTIATOR),
            Axis(name="population", description="regional cohort", role=AxisRole.CONTEXT),
        ],
    )


def _ficha(ref, title, matches, **kw) -> Ficha:
    return Ficha(paper_ref=ref, title=title, axis_matches=matches, **kw)


def test_profile_requires_differentiator():
    with pytest.raises(ValueError, match="differentiator"):
        NoveltyProfile(
            paper_ref="x",
            axes=[Axis(name="d", description="y", role=AxisRole.CORE)],
        )


def test_tier_assignment():
    p = _profile()
    t1 = _ficha("a", "Full match", {"domain": True, "modality": True, "xai": True})
    t2 = _ficha("b", "Twin", {"domain": True, "modality": True, "xai": False})
    t3 = _ficha("c", "Anchor", {"domain": False, "modality": False, "xai": True})
    t4 = _ficha("d", "Context", {"domain": False, "modality": False, "xai": False, "population": True})
    ranked = tier_papers(p, [t4, t3, t2, t1])
    by_ref = {f.paper_ref: f for f in ranked}
    assert (by_ref["a"].tier, by_ref["a"].threat) == (Tier.T1, Threat.HIGH)
    assert (by_ref["b"].tier, by_ref["b"].threat) == (Tier.T2, Threat.MEDIUM)
    assert (by_ref["c"].tier, by_ref["c"].threat) == (Tier.T3, Threat.LOW)
    assert (by_ref["d"].tier, by_ref["d"].threat) == (Tier.T4, Threat.CONTEXT)


def test_ranked_t1_first():
    p = _profile()
    t4 = _ficha("d", "Context", {"population": True})
    t1 = _ficha("a", "Full", {"domain": True, "modality": True, "xai": True})
    ranked = tier_papers(p, [t4, t1])
    assert ranked[0].paper_ref == "a"


def test_dedup_by_doi():
    a = _ficha("a", "Paper A", {}, doi="10.1/x")
    b = _ficha("b", "Paper A dup", {}, doi="https://doi.org/10.1/X")  # same DOI, different case/prefix
    assert len(dedup_fichas([a, b])) == 1


def test_dedup_by_title_year_when_no_doi():
    a = _ficha("a", "Same Title", {}, year=2024)
    b = _ficha("b", "same title", {}, year=2024)
    c = _ficha("c", "Same Title", {}, year=2023)  # different year -> kept
    out = dedup_fichas([a, b, c])
    assert len(out) == 2
