from rag_research.litreview import Axis, AxisRole, Ficha, NoveltyProfile, tier_papers
from rag_research.report import render_reporte, render_v2


def _setup():
    profile = NoveltyProfile(
        paper_ref="demo2025",
        axes=[
            Axis(name="domain", description="lesion detection", role=AxisRole.CORE),
            Axis(name="modality", description="MRI+CT", role=AxisRole.CORE),
            Axis(name="xai", description="concept attribution", role=AxisRole.DIFFERENTIATOR),
        ],
    )
    fichas = [
        Ficha(paper_ref="a", title="Alpha-Net", year=2026, venue="MICCAI", doi="10.1/a",
              modalities=["MRI", "CT"], is_multimodal=True, xai_techniques=["attention"],
              pdf_status="paywall", axis_matches={"domain": True, "modality": True, "xai": True},
              relation_to_paper="competidor cercano"),
        Ficha(paper_ref="b", title="Beta-Net", year=2024, venue="OMIA", pdf_status="local",
              modalities=["MRI", "CT"], is_multimodal=True,
              axis_matches={"domain": True, "modality": True, "xai": False}),
        Ficha(paper_ref="c", title="Gamma-Net", year=2021, pdf_status="paywall",
              xai_techniques=["concept attribution"], axis_matches={"domain": False, "modality": False, "xai": True}),
    ]
    return profile, tier_papers(profile, fichas)


def test_render_reporte_structure():
    profile, fichas = _setup()
    md = render_reporte(profile, fichas)
    assert md.startswith("# Estado del Arte — demo2025")
    assert "## 1. Perfil de novedad" in md
    assert "T1 — Competidores directos" in md
    assert "Alpha-Net" in md
    assert "## 3. Accionables" in md
    assert "Diferenciar explícitamente frente a Alpha-Net." in md
    assert "verify_claim_against_corpus" in md
    # papers without a local PDF are flagged
    assert "## 4. Sin PDF local" in md
    assert "Gamma-Net" in md


def test_render_v2_sells_the_differentiator():
    profile, fichas = _setup()
    md = render_v2(profile, fichas)
    assert "## Novedad real a vender" in md
    assert "concept attribution" in md
    assert "🟢 alta" in md  # Beta-Net has a local PDF
    assert "🟡 media" in md  # Alpha-Net is paywalled


def test_confidence_reflects_pdf():
    profile, fichas = _setup()
    md = render_reporte(profile, fichas)
    # local PDF -> high confidence appears somewhere
    assert "🟢 alta" in md
