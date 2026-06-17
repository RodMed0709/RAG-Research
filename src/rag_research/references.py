"""BibTeX generation and missing-citation detection from fichas. Deterministic, pure."""
from __future__ import annotations

import re

from .consistency import Finding, Severity
from .litreview import Ficha, Tier

_CONF_MARKERS = (
    "conf", "proceedings", "workshop", "symposium",
    "miccai", "cvpr", "iccv", "neurips", "icml",
)


def _alnum(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _last_name(author: str) -> str:
    author = author.strip()
    if "," in author:                      # "Doe, Jane"
        return author.split(",", 1)[0]
    return author.split()[-1] if author.split() else author


def _bibtex_key(ficha: Ficha) -> str:
    if ficha.authors:
        base = _alnum(_last_name(ficha.authors[0]))
    else:
        base = _alnum(ficha.paper_ref)
    if ficha.year:
        base = f"{base}{ficha.year}"
    return base or "ref"


def ficha_to_bibtex(ficha: Ficha) -> str:
    venue = ficha.venue or ""
    is_conf = any(m in venue.lower() for m in _CONF_MARKERS)
    entry_type = "@inproceedings" if is_conf else "@article"
    venue_field = "booktitle" if is_conf else "journal"

    fields: list[tuple[str, str]] = []
    if ficha.title:
        fields.append(("title", ficha.title))
    if ficha.authors:
        fields.append(("author", " and ".join(ficha.authors)))
    if ficha.year:
        fields.append(("year", str(ficha.year)))
    if venue:
        fields.append((venue_field, venue))
    if ficha.doi:
        fields.append(("doi", ficha.doi))
    if ficha.github_url:
        fields.append(("note", f"Code: {ficha.github_url}"))

    body = ",\n".join(f"  {k} = {{{v}}}" for k, v in fields)
    return f"{entry_type}{{{_bibtex_key(ficha)},\n{body}\n}}"


def build_bibliography(fichas: list[Ficha]) -> str:
    return "\n\n".join(ficha_to_bibtex(f) for f in fichas if f.title)


def detect_missing_citations(cited_refs: list[str], fichas: list[Ficha]) -> list[Finding]:
    """Flag T1/T2 papers the manuscript does not yet cite. A paper counts as cited if its
    title OR DOI appears (case-insensitive substring) in any of the cited reference strings."""
    cited_low = [c.lower() for c in cited_refs]
    findings: list[Finding] = []
    for f in fichas:
        if f.tier not in (Tier.T1, Tier.T2):
            continue
        needles = [n.lower() for n in (f.title, f.doi) if n]
        if any(any(n in c for c in cited_low) for n in needles):
            continue
        findings.append(
            Finding(
                severity=Severity.MAJOR if f.tier == Tier.T1 else Severity.MINOR,
                category="citation",
                message=f"No citado ({f.tier.value}): {f.title}.",
                suggestion="Añadir cita y diferenciar/contrastar.",
            )
        )
    return findings
