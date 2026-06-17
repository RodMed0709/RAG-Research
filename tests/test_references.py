from rag_research.consistency import Severity
from rag_research.litreview import Ficha, Tier
from rag_research.references import (
    build_bibliography,
    detect_missing_citations,
    ficha_to_bibtex,
)


def _ficha(**kw) -> Ficha:
    base = dict(paper_ref="x", title="A Paper", authors=["Doe, Jane"], year=2024)
    base.update(kw)
    return Ficha(**base)


def test_bibtex_article():
    bib = ficha_to_bibtex(_ficha(venue="IEEE TBME", doi="10.1/x"))
    assert bib.startswith("@article{doe2024,")
    assert "author = {Doe, Jane}" in bib
    assert "journal = {IEEE TBME}" in bib
    assert "doi = {10.1/x}" in bib


def test_bibtex_inproceedings_detected():
    bib = ficha_to_bibtex(_ficha(venue="MICCAI 2024 Workshop"))
    assert bib.startswith("@inproceedings{")
    assert "booktitle = {MICCAI 2024 Workshop}" in bib


def test_bibtex_github_note():
    bib = ficha_to_bibtex(_ficha(github_url="github.com/x/y"))
    assert "note = {Code: github.com/x/y}" in bib


def test_build_bibliography_skips_empty_title():
    fichas = [_ficha(title="Real"), Ficha(paper_ref="e", title="")]
    bib = build_bibliography(fichas)
    assert bib.count("@") == 1


def test_missing_citations_t1_major():
    t1 = _ficha(paper_ref="g", title="Alpha-Net", doi="10.1/g", tier=Tier.T1)
    t2 = _ficha(paper_ref="e", title="Beta-Net", doi="10.1/e", tier=Tier.T2)
    t3 = _ficha(paper_ref="t", title="Gamma-Net", tier=Tier.T3)  # not checked
    out = detect_missing_citations(cited_refs=["Some other ref 2020"], fichas=[t1, t2, t3])
    sev = {f.message: f.severity for f in out}
    assert any("Alpha-Net" in m for m in sev)
    assert any("Beta-Net" in m for m in sev)
    assert all("Gamma-Net" not in m for m in sev)  # T3 ignored
    major = next(f for f in out if "Alpha-Net" in f.message)
    assert major.severity == Severity.MAJOR


def test_already_cited_not_flagged():
    t1 = _ficha(paper_ref="g", title="Alpha-Net", doi="10.1/g", tier=Tier.T1)
    out = detect_missing_citations(cited_refs=["Alpha-Net multimodal 2026"], fichas=[t1])
    assert out == []
