"""WRITE-from-code — pillar 4. Draft a paper's Methods straight from a code repo, with every
sentence anchored to a verbatim line of code.

The mirror image of the code↔paper check: that pillar *verifies* that code honors a paper;
this *writes* the paper's Methods FROM the code. The anti-hallucination guarantee is even stronger
here than in WRITE-from-papers — it is DETERMINISTIC, not judge-based: a Methods sentence
about an aspect (batch_size, lr, augmentation, ...) is written ONLY if the value the writer
states is pinned verbatim in an actual line of code. If the value cannot be located in the
source, the aspect comes back NO_EVIDENCE — never asserted from the model's imagination.
"""
from __future__ import annotations

from enum import Enum
from typing import Callable

from pydantic import BaseModel


class CodeStatus(str, Enum):
    ANCHORED = "anchored"          # value pinned in a code line -> sentence written
    NO_EVIDENCE = "no_evidence"    # not found in the code -> marked, not written


# Injected: locate the literal value of an aspect in the code (bare value or None).
CodeValueLocator = Callable[[str, str], "str | None"]      # (aspect, code) -> value | None
# Injected: write ONE Methods sentence for an aspect, given its value and the code line.
CodeWriter = Callable[[str, str, str], str]                # (aspect, value, code_line) -> str


class CodeClaim(BaseModel):
    aspect: str
    claim_text: str
    value: str | None = None
    code_line: str | None = None
    lineno: int | None = None
    status: CodeStatus


class MethodsDraft(BaseModel):
    claims: list[CodeClaim]

    def anchored(self) -> list[CodeClaim]:
        return [c for c in self.claims if c.status == CodeStatus.ANCHORED]

    def no_evidence_count(self) -> int:
        """Aspects we refused to write because the code does not state them — the headline
        anti-hallucination signal (mirror of ``DraftSection.no_evidence_count``)."""
        return sum(1 for c in self.claims if c.status == CodeStatus.NO_EVIDENCE)


def _find_line(code: str, value: str, aspect: str = "") -> tuple[str, int] | None:
    """A code line that contains ``value`` verbatim, with its 1-based line number. Prefers a
    line that ALSO mentions a token of the aspect (kills homonyms like "8" matching "0.8" on an
    unrelated line); otherwise falls back to the first verbatim match. No match -> no claim."""
    tokens = [t for t in aspect.lower().replace("_", " ").split() if t]
    hits = [(line.strip(), i) for i, line in enumerate(code.splitlines(), 1) if value in line]
    if not hits:
        return None
    for line, i in hits:
        low = line.lower()
        if any(t in low for t in tokens):
            return line, i
    return hits[0]


def draft_code_claim(
    aspect: str, code: str, *, locate: CodeValueLocator, write: CodeWriter
) -> CodeClaim:
    """Locate -> pin verbatim -> write. The writer phrases it; the verbatim pin authorizes it."""
    value = locate(aspect, code)
    if value is None:
        return CodeClaim(aspect=aspect, claim_text="", status=CodeStatus.NO_EVIDENCE)

    hit = _find_line(code, value, aspect)
    if hit is None:
        # The locator named a value we cannot pin in the source verbatim. Refuse to assert it
        # — that refusal IS the guarantee (mirrors make_jumper returning None).
        return CodeClaim(aspect=aspect, claim_text="", value=value, status=CodeStatus.NO_EVIDENCE)

    code_line, lineno = hit
    claim_text = write(aspect, value, code_line)
    return CodeClaim(
        aspect=aspect,
        claim_text=claim_text,
        value=value,
        code_line=code_line,
        lineno=lineno,
        status=CodeStatus.ANCHORED,
    )


def draft_methods(
    aspects: list[str], code: str, *, locate: CodeValueLocator, write: CodeWriter
) -> MethodsDraft:
    """Draft a Methods claim per aspect, independently. Order preserved."""
    return MethodsDraft(
        claims=[draft_code_claim(a, code, locate=locate, write=write) for a in aspects]
    )


_EMOJI = {CodeStatus.ANCHORED: "✅", CodeStatus.NO_EVIDENCE: "❌"}


def render_methods(draft: MethodsDraft, title: str = "Methods") -> str:
    """Pure Markdown: the Methods prose, plus a traceability appendix mapping each aspect to
    the exact code line it was drawn from. NO_EVIDENCE aspects stay visible."""
    lines = [f"# {title}", "", "## Prosa", ""]

    prose: list[str] = []
    for c in draft.claims:
        if c.status == CodeStatus.ANCHORED:
            prose.append(c.claim_text)
        else:
            if prose:
                lines.append(" ".join(prose))
                lines.append("")
                prose = []
            lines.append(f"> [SIN EVIDENCIA EN CÓDIGO: {c.aspect}]")
            lines.append("")
    if prose:
        lines.append(" ".join(prose))
        lines.append("")

    lines += ["## Trazabilidad (código)", ""]
    for c in draft.claims:
        emoji = _EMOJI[c.status]
        if c.status == CodeStatus.ANCHORED:
            loc = f"L{c.lineno}" if c.lineno is not None else "?"
            lines.append(f"- {emoji} **{c.aspect}** = `{c.value}` → {loc}: `{c.code_line}`")
        else:
            lines.append(f"- {emoji} **{c.aspect}** — no aparece en el código")
    lines.append("")

    total = len(draft.claims)
    lines.append(f"**Sin evidencia en código: {draft.no_evidence_count()} de {total} aspectos.**")
    return "\n".join(lines)
