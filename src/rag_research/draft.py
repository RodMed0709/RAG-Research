"""WRITE-from-papers — the inverse of the REVIEW pillar.

REVIEW takes a claim and *verifies* it (``verify_claim`` -> HONORED only with a verbatim
anchor). WRITE inverts the flow: it takes an outline bullet, *retrieves evidence* from the
corpus, asks an injected writer LLM for a sentence grounded ONLY in that evidence, and then
runs the SAME anti-hallucination engine over the result. The verdict of "is this sentence
supported?" comes from ``verify_claim`` (code), NEVER from the writer's own word.

Invariants:
1. A sentence reaches the prose only if ``verify_claim`` returns HONORED with a verbatim
   anchor — the writer is never trusted to self-certify.
2. NO_EVIDENCE is always VISIBLE in the rendered output, never silently dropped.
"""
from __future__ import annotations

from enum import Enum
from typing import Callable

from pydantic import BaseModel

from .claim import Claim, ClaimKind, ClaimVerdict
from .claimverify import ClaimExtractor, ClaimJudge, Retriever, verify_claim
from .speccard import Jumper


class DraftStatus(str, Enum):
    ANCHORED = "anchored"          # sentence backed by a verbatim anchor -> enters prose
    NO_EVIDENCE = "no_evidence"    # nothing in the corpus supports it -> marked, not written
    AMBIGUOUS = "ambiguous"        # human queue (e.g. numeric without verbatim pin)


# Injected writer LLM: (bullet, passage_texts) -> a single prose sentence grounded only in
# the passages. Its output is a CANDIDATE — the verdict is decided downstream by verify_claim.
Writer = Callable[[str, list[str]], str]


class DraftCard(BaseModel):
    """One outline bullet turned into a candidate sentence + its verification trace."""

    bullet: str
    claim_text: str
    jumper: Jumper | None = None
    source: str | None = None
    status: DraftStatus


class DraftSection(BaseModel):
    cards: list[DraftCard]

    def anchored(self) -> list[DraftCard]:
        return [c for c in self.cards if c.status == DraftStatus.ANCHORED]

    def no_evidence_count(self) -> int:
        """Bullets we refused to write — the headline anti-hallucination signal (mirror of
        ``ClaimCard.unsupported_count``)."""
        return sum(1 for c in self.cards if c.status == DraftStatus.NO_EVIDENCE)


def draft_bullet(
    bullet: str,
    *,
    retrieve: Retriever,
    write: Writer,
    judge: ClaimJudge,
    extractor: ClaimExtractor,
    k: int = 8,
    claim_id: str = "draft",
) -> DraftCard:
    """Retrieve -> write -> verify -> map. The writer proposes; ``verify_claim`` disposes."""
    passages = retrieve(bullet, k)
    if not passages:
        # Nothing in the corpus speaks to this bullet: refuse to write (no exception).
        return DraftCard(bullet=bullet, claim_text="", status=DraftStatus.NO_EVIDENCE)

    claim_text = write(bullet, [p.verbatim_text for p in passages])

    # CITATION kind routes verify_claim to the injected judge against the retrieved passages,
    # catching a writer that strays beyond them. No value_spec needed for prose support.
    claim = Claim(claim_id=claim_id, text=claim_text, kind=ClaimKind.CITATION)
    verify_claim(claim, retrieve=retrieve, judge=judge, extractor=extractor, k=k)

    anchor = claim.evidence[0] if claim.evidence else None
    if claim.verdict == ClaimVerdict.HONORED and anchor is not None:
        status = DraftStatus.ANCHORED
    elif claim.verdict == ClaimVerdict.AMBIGUOUS:
        status = DraftStatus.AMBIGUOUS
    else:  # UNSUPPORTED / CONTRADICTED — not grounded, do not write
        return DraftCard(bullet=bullet, claim_text=claim_text, status=DraftStatus.NO_EVIDENCE)

    return DraftCard(
        bullet=bullet,
        claim_text=claim_text,
        jumper=anchor,
        source=passages[0].doc_citation or None,
        status=status,
    )


def draft_section(
    outline: list[str],
    *,
    retrieve: Retriever,
    write: Writer,
    judge: ClaimJudge,
    extractor: ClaimExtractor,
    k: int = 8,
) -> DraftSection:
    """Draft every bullet independently. Order preserved; ids are 1-based."""
    cards = [
        draft_bullet(
            b, retrieve=retrieve, write=write, judge=judge,
            extractor=extractor, k=k, claim_id=f"draft-{i}",
        )
        for i, b in enumerate(outline, 1)
    ]
    return DraftSection(cards=cards)


_EMOJI = {
    DraftStatus.ANCHORED: "✅",
    DraftStatus.AMBIGUOUS: "⚠️",
    DraftStatus.NO_EVIDENCE: "❌",
}


def render_draft_section(section: DraftSection, title: str = "Section") -> str:
    """Pure Markdown: anchored prose with inline citations, NO_EVIDENCE markers kept visible,
    and a traceability appendix mapping each bullet to its verbatim anchor."""
    lines = [f"# {title}", "", "## Prosa", ""]

    prose: list[str] = []
    for c in section.cards:
        if c.status == DraftStatus.ANCHORED:
            cite = f" [{c.source}]" if c.source else ""
            prose.append(f"{c.claim_text}{cite}")
        elif c.status == DraftStatus.AMBIGUOUS:
            prose.append(f"{c.claim_text} [⚠️ revisar]")
        else:  # NO_EVIDENCE — visible, on its own line
            if prose:
                lines.append(" ".join(prose))
                lines.append("")
                prose = []
            lines.append(f"> [SIN EVIDENCIA: {c.bullet}]")
            lines.append("")
    if prose:
        lines.append(" ".join(prose))
        lines.append("")

    lines += ["## Trazabilidad (draft-cards)", ""]
    for c in section.cards:
        emoji = _EMOJI[c.status]
        if c.status == DraftStatus.NO_EVIDENCE:
            lines.append(f"- {emoji} {c.bullet}")
        else:
            anchor = (c.jumper.anchor_phrase[:120] + "…") if c.jumper and len(c.jumper.anchor_phrase) > 120 else (c.jumper.anchor_phrase if c.jumper else "—")
            src = f" — {c.source}" if c.source else ""
            lines.append(f"- {emoji} {c.bullet} → «{anchor}»{src}")
    lines.append("")

    total = len(section.cards)
    lines.append(f"**Sin evidencia: {section.no_evidence_count()} de {total} bullets.**")
    return "\n".join(lines)
