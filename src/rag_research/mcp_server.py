"""rag_research MCP server (the ``[mcp]`` extra).

Lets another Claude Code session / agent use rag_research as a grounded verification tool:
Claude orchestrates, rag_research (with DeepSeek inside) does the grounded, traceable check. The
calling model never has to hold reproducibility norms in its volatile memory — it asks this
tool, which compares against typed spec-cards.

Run directly:  python -m rag_research.mcp_server
Or register in an MCP client (e.g. Claude Code) pointing at that command. Needs the ``[mcp]``
extra (fastmcp) and ``DEEPSEEK_API_KEY`` in the environment / a local ``.env``.
"""
from __future__ import annotations

from pathlib import Path

from fastmcp import FastMCP

import json

from .claim import Claim, ClaimCard
from .claimverify import verify_claimcard
from .codegen import Stamp, check_stamp
from .consistency import (
    Finding,
    confusion_matrix_check,
    detect_missing_sections,
    detect_terminology_variants,
    render_review,
)
from .litreview import Ficha, NoveltyProfile
from .litreview import tier_papers as _tier_papers
from .delivery import (
    TrackedChange,
    render_latex_changes,
    render_tracked_changes,
)
from .references import build_bibliography, detect_missing_citations
from .report import md_to_docx, render_reporte, render_v2
from .speccard import SpecCard
from .verify import FieldVerdict, verify_consistency

mcp: FastMCP = FastMCP("RAG-Research")


def _verdict_dict(v: FieldVerdict) -> dict[str, object]:
    return {
        "field": v.field_name,
        "state": v.state.value,
        "blocked": v.blocked,
        "needs_human": v.needs_human,
        "source": v.verdict_source,
        "code_evidence": v.code_evidence,
    }


def _load_keys() -> None:
    """Find DEEPSEEK_API_KEY's .env whether the server is launched from the project dir or
    elsewhere (an MCP client may spawn it with any cwd)."""
    from .llm import load_env

    here = Path(__file__).resolve()
    for candidate in (Path.cwd() / ".env", here.parents[2] / ".env"):
        load_env(candidate)


def _verify(card_json: str, code: str) -> dict[str, object]:
    from .llm import make_judge, make_locator

    _load_keys()
    card = SpecCard.model_validate_json(card_json)
    verdicts = verify_consistency(card, code, locate=make_locator(), judge=make_judge())
    blocked = any(v.blocked for v in verdicts)
    human = any(v.needs_human for v in verdicts)
    outcome = "blocked" if blocked else ("held_for_human" if human else "ok")
    return {
        "card_id": card.card_id,
        "version": card.version,
        "outcome": outcome,
        "verdicts": [_verdict_dict(v) for v in verdicts],
    }


@mcp.tool
def verify_code_against_card(card_json: str, code: str) -> dict[str, object]:
    """Verify a code snippet against a spec-card (JSON string).

    Hard fields (batch_size, lr, ...) are compared DETERMINISTICALLY; only semantic fields
    (e.g. augmentation phase) go to the LLM. Returns per-field verdicts and an overall
    ``outcome``: ``ok`` / ``held_for_human`` / ``blocked``. Use before trusting generated ML
    code: it tells you, traceably, which of the paper's reproducibility norms the code honors.
    """
    return _verify(card_json, code)


@mcp.tool
def verify_file_against_card(card_path: str, code_path: str) -> dict[str, object]:
    """Like ``verify_code_against_card`` but reads the spec-card JSON and the code from file paths."""
    card_json = Path(card_path).read_text(encoding="utf-8")
    code = Path(code_path).read_text(encoding="utf-8")
    return _verify(card_json, code)


@mcp.tool
def check_code_stamp(stamp_json: str, current_card_json: str) -> dict[str, object]:
    """Check whether code stamped against an earlier card version is now STALE.

    Pass the stamp (JSON) the code was generated with and the current spec-card (JSON). Returns
    whether the code drifted (a value/phase/field changed on re-extraction) and which fields.
    """
    stamp = Stamp.model_validate_json(stamp_json)
    card = SpecCard.model_validate_json(current_card_json)
    report = check_stamp(stamp, card)
    return {"stale": report.stale, "reason": report.reason, "changed_fields": report.changed_fields}


def _claim_dict(c: Claim) -> dict[str, object]:
    return {
        "claim_id": c.claim_id,
        "text": c.text,
        "kind": c.kind.value,
        "verdict": c.verdict.value if c.verdict is not None else None,
        "location": c.location,
        "evidence": [
            {
                "anchor_phrase": j.anchor_phrase,
                "verbatim_text": j.verbatim_text,
                "page_range": j.page_range,
            }
            for j in c.evidence
        ],
    }


@mcp.tool
async def verify_claim_against_corpus(
    claim_card_json: str, corpus_paths: list[str], k: int = 8
) -> dict[str, object]:
    """Verify a claim-card (manuscript assertions, JSON) against a corpus of source PDFs.

    Each claim is checked against verbatim passages retrieved from the corpus: NUMERIC /
    COMPARATIVE claims are compared DETERMINISTICALLY, the rest judged by the LLM grounded
    ONLY in the passages. A claim is HONORED only if it carries a verbatim anchor; otherwise
    it is UNSUPPORTED — the anti-hallucination signal. Returns per-claim verdicts with
    evidence and a summary. Needs the ``[paperqa]`` extra and ``DEEPSEEK_API_KEY``.
    """
    from .llm import make_claim_extractor, make_claim_judge
    from .substrate import Substrate

    _load_keys()
    card = ClaimCard.model_validate_json(claim_card_json)
    sub = Substrate()
    for path in corpus_paths:
        await sub.ingest(path)

    # Pre-retrieve per claim so verify_claim can stay synchronous (mirrors verify.py).
    cache: dict[str, list[object]] = {}
    for claim in card.claims:
        cache[claim.text] = await sub.retrieve(claim.text, k)

    def retrieve(query: str, _k: int) -> list[object]:
        return cache.get(query, [])  # type: ignore[return-value]

    verify_claimcard(
        card, retrieve=retrieve, judge=make_claim_judge(), extractor=make_claim_extractor(), k=k
    )

    verdicts = [c.verdict.value if c.verdict is not None else "none" for c in card.claims]
    summary = {
        "honored": verdicts.count("honored"),
        "contradicted": verdicts.count("contradicted"),
        "unsupported": verdicts.count("unsupported"),
        "ambiguous": verdicts.count("ambiguous"),
    }
    return {
        "card_id": card.card_id,
        "manuscript_ref": card.manuscript_ref,
        "summary": summary,
        "claims": [_claim_dict(c) for c in card.claims],
    }


def _parse_fichas(fichas_json: str) -> list[Ficha]:
    return [Ficha.model_validate(x) for x in json.loads(fichas_json)]


@mcp.tool
def tier_papers(profile_json: str, fichas_json: str, core_threshold: float = 0.6) -> dict[str, object]:
    """Tier literature fichas against a paper's novelty profile, deterministically.

    ``profile_json`` is a NoveltyProfile (axes with roles core/differentiator/context);
    ``fichas_json`` is a JSON array of fichas (each with ``axis_matches``). Dedups by DOI /
    title, assigns T1-T4 + threat by rule, and returns fichas sorted by importance. Same
    input -> same tiers (no LLM in the ranking). Use before rendering a state-of-the-art.
    """
    profile = NoveltyProfile.model_validate_json(profile_json)
    fichas = _parse_fichas(fichas_json)
    ranked = _tier_papers(profile, fichas, core_threshold=core_threshold)
    return {
        "paper_ref": profile.paper_ref,
        "count": len(ranked),
        "fichas": [f.model_dump(mode="json") for f in ranked],
    }


@mcp.tool
def render_report(profile_json: str, fichas_json: str, kind: str = "full") -> dict[str, object]:
    """Render a state-of-the-art report as Markdown. ``kind`` = ``full`` (REPORTE.md: novelty
    matrix, tier tables, actionables) or ``v2`` (condensed, publication-ready, confidence
    labels). Fichas should already be tiered (run ``tier_papers`` first). Returns the markdown.
    """
    profile = NoveltyProfile.model_validate_json(profile_json)
    fichas = _parse_fichas(fichas_json)
    md = render_v2(profile, fichas) if kind == "v2" else render_reporte(profile, fichas)
    return {"kind": kind, "markdown": md}


@mcp.tool
def check_consistency(config_json: str) -> dict[str, object]:
    """Run deterministic internal-consistency checks on a manuscript and return findings +
    a rendered REVIEW.md. ``config_json`` keys (all optional):
    ``text`` + ``terminology_groups`` (list of equivalent-spelling groups) for terminology;
    ``confusion`` ({tp,fp,fn,tn}) + ``claimed_metrics`` ({recall,precision,accuracy}) for the
    metric recompute; ``sections_present`` + ``sections_required`` for structure. No LLM.
    """
    cfg = json.loads(config_json)
    findings: list[Finding] = []
    text = cfg.get("text")
    groups = cfg.get("terminology_groups")
    if text is not None and groups:
        findings += detect_terminology_variants(text, groups)
    cm = cfg.get("confusion")
    claimed = cfg.get("claimed_metrics")
    if cm and claimed:
        findings += confusion_matrix_check(
            int(cm["tp"]), int(cm["fp"]), int(cm["fn"]), int(cm["tn"]), claimed,
            atol=float(cfg.get("atol", 0.01)),
        )
    present = cfg.get("sections_present")
    required = cfg.get("sections_required")
    if present is not None and required:
        findings += detect_missing_sections(present, required)

    return {
        "count": len(findings),
        "findings": [f.model_dump(mode="json") for f in findings],
        "review_md": render_review(findings, title=cfg.get("title", "Revisión de consistencia")),
    }


@mcp.tool
def build_bibliography_tool(fichas_json: str, cited_refs: list[str] | None = None) -> dict[str, object]:
    """Build a BibTeX bibliography from fichas, and (if ``cited_refs`` is given — the
    references the manuscript already cites) flag the T1/T2 papers still missing a citation.
    """
    fichas = _parse_fichas(fichas_json)
    missing = detect_missing_citations(cited_refs, fichas) if cited_refs is not None else []
    return {
        "bibtex": build_bibliography(fichas),
        "missing_citations": [m.model_dump(mode="json") for m in missing],
    }


@mcp.tool
def render_changes(changes_json: str, title: str = "Cambios marcados") -> dict[str, object]:
    """Render tracked changes for the reviewer hand-off. ``changes_json`` is a JSON array of
    {before, after, reason, location?}. Returns ``markdown`` (CAMBIOS_MARCADOS.md, ❌/✅/💡)
    and ``latex`` (inline tracked-change markup ready to paste into an Overleaf project).
    """
    changes = [TrackedChange.model_validate(x) for x in json.loads(changes_json)]
    return {
        "markdown": render_tracked_changes(changes, title=title),
        "latex": render_latex_changes(changes),
    }


@mcp.tool
async def draft_section_tool(
    outline: list[str], corpus_paths: list[str], title: str = "Section", k: int = 8
) -> dict[str, object]:
    """WRITE-from-papers: draft a paper section from an outline, grounded in a corpus.

    For each bullet, retrieves verbatim passages from the corpus PDFs, writes one sentence
    grounded ONLY in them, then re-verifies it with the anti-hallucination engine: a sentence
    enters the prose only if it earns a verbatim anchor (status ANCHORED). Bullets without
    support come back as NO_EVIDENCE — visible, never invented. Returns the rendered Markdown
    section, per-bullet draft-cards, and a count of unsupported bullets. Needs the
    ``[paperqa]`` extra and ``DEEPSEEK_API_KEY``.
    """
    from .draft import draft_section, render_draft_section
    from .llm import make_claim_extractor, make_claim_judge, make_writer
    from .substrate import Substrate

    _load_keys()
    sub = Substrate()
    for path in corpus_paths:
        await sub.ingest(path)

    # Pre-retrieve per query (bullets AND, indirectly, the written sentences) so the engine
    # stays synchronous. We cache on the query string used at each retrieve call site.
    cache: dict[str, list[object]] = {}

    async def _warm(query: str) -> None:
        if query not in cache:
            cache[query] = await sub.retrieve(query, k)  # type: ignore[assignment]

    for bullet in outline:
        await _warm(bullet)

    def retrieve(query: str, _k: int) -> list[object]:
        return cache.get(query, [])  # type: ignore[return-value]

    # verify_claim re-retrieves with the WRITTEN sentence, so its retrieval must be warm
    # before the sync draft runs. Write each sentence once and MEMOIZE it: draft_section then
    # reuses the exact same sentence (not a re-generated, possibly-different one), so the
    # warmed retrieval cache always hits. Without memoization a non-deterministic LLM could
    # yield a second sentence whose query was never warmed -> a false NO_EVIDENCE.
    _raw_writer = make_writer()
    _memo: dict[str, str] = {}

    def writer(bullet: str, passage_texts: list[str]) -> str:
        if bullet not in _memo:
            _memo[bullet] = _raw_writer(bullet, passage_texts)
        return _memo[bullet]

    for bullet in outline:
        sentence = writer(bullet, [p.verbatim_text for p in cache.get(bullet, [])])  # type: ignore[attr-defined]
        await _warm(sentence)

    section = draft_section(
        outline, retrieve=retrieve, write=writer,
        judge=make_claim_judge(), extractor=make_claim_extractor(), k=k,
    )
    return {
        "title": title,
        "no_evidence_count": section.no_evidence_count(),
        "total": len(section.cards),
        "markdown": render_draft_section(section, title=title),
        "cards": [c.model_dump(mode="json") for c in section.cards],
    }


def _draft_methods(aspects: list[str], code: str, title: str) -> dict[str, object]:
    from .codewrite import draft_methods, render_methods
    from .llm import make_code_locator, make_code_writer

    _load_keys()
    draft = draft_methods(aspects, code, locate=make_code_locator(), write=make_code_writer())
    return {
        "title": title,
        "no_evidence_count": draft.no_evidence_count(),
        "total": len(draft.claims),
        "markdown": render_methods(draft, title=title),
        "claims": [c.model_dump(mode="json") for c in draft.claims],
    }


@mcp.tool
def draft_methods_tool(aspects: list[str], code: str, title: str = "Methods") -> dict[str, object]:
    """WRITE-from-code: draft a paper's Methods straight from a code repo dump.

    For each aspect (batch_size, lr, augmentation, normalization, architecture, ...), locates
    its value in the code and writes ONE Methods sentence — but only if the value is pinned
    VERBATIM in a real code line (deterministic anchor). Aspects the code does not set come
    back NO_EVIDENCE — visible, never invented. Returns the rendered Methods, per-aspect
    claims with code line + line number, and a count of unsupported aspects. Needs
    ``DEEPSEEK_API_KEY``.
    """
    return _draft_methods(aspects, code, title)


@mcp.tool
def draft_methods_from_file(
    aspects: list[str], code_path: str, title: str = "Methods"
) -> dict[str, object]:
    """Like ``draft_methods_tool`` but reads the code from a file path."""
    return _draft_methods(aspects, Path(code_path).read_text(encoding="utf-8"), title)


@mcp.tool
def export_docx(markdown: str, out_path: str) -> dict[str, object]:
    """Export a Markdown string to a .docx file at ``out_path`` (needs python-docx). Use for
    REPORTE / REVIEW / CAMBIOS_MARCADOS Word deliverables. Returns the written path."""
    path = md_to_docx(markdown, out_path)
    return {"path": path}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
