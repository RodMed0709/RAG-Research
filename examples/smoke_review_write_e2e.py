"""End-to-end smoke for the REVIEW + WRITE jobs against a LIVE corpus and a real LLM.

Ingests one open-access paper into the PaperQA2 substrate (local embeddings, offline retrieval)
and exercises the anchored-or-flagged guarantee with a real DeepSeek LLM:

  REVIEW  -> verify_claim over a true / false / methodological claim
  WRITE   -> draft a section from bullets (one supported, one not)

It is NOT a unit test (those use fakes and run in CI). This is the production-path check the
README's "honest caveat" asks for. Bring the paper yourself and a DEEPSEEK_API_KEY in .env.

    python examples/smoke_review_write_e2e.py [path/to/paper.pdf]

Default paper: smoke_corpus/attention.pdf (download: arxiv.org/pdf/1706.03762).
"""
from __future__ import annotations

import asyncio
import sys

# Windows consoles default to cp1252 and choke on the ✅/❌ markers in the rendered output.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except Exception:
    pass

from rag_research.claim import Claim, ClaimCard, ClaimKind
from rag_research.claimverify import verify_claimcard
from rag_research.draft import draft_section, render_draft_section
from rag_research.llm import (
    load_env,
    make_claim_extractor,
    make_claim_judge,
    make_writer,
)
from rag_research.speccard import ValueKind, ValueSpec
from rag_research.substrate import Substrate

PAPER = sys.argv[1] if len(sys.argv) > 1 else "smoke_corpus/attention.pdf"


def _hr(title: str) -> None:
    print("\n" + "=" * 70 + f"\n{title}\n" + "=" * 70)


async def main() -> None:
    load_env(".env")

    _hr(f"INGEST  ·  {PAPER}")
    sub = Substrate()
    ref = await sub.ingest(PAPER, paper_ref="paper")
    probe = await sub.retrieve("model architecture", 3)
    print(f"ingested as {ref!r} · retrieval returns {len(probe)} passages for a probe query")
    if not probe:
        print("!! no passages retrieved — parsing/ingest failed, aborting"); return

    judge = make_claim_judge()
    extractor = make_claim_extractor()

    # ---------------- REVIEW: verify three claims of known polarity ----------------
    _hr("REVIEW  ·  verify_claim (true / false / methodological)")
    claims = [
        Claim(  # TRUE numeric fact: the paper sets h = 8 heads
            claim_id="c1",
            text="The Transformer uses 8 parallel attention heads.",
            kind=ClaimKind.NUMERIC_FACT,
            value_spec=ValueSpec(kind=ValueKind.NUMERIC, equals=8),
        ),
        Claim(  # UNSUPPORTED: this paper is about translation, not ImageNet
            claim_id="c2",
            text="The model was trained on the ImageNet dataset for image classification.",
            kind=ClaimKind.CITATION,
        ),
        Claim(  # TRUE methodological: self-attention replaces recurrence
            claim_id="c3",
            text="The architecture relies on self-attention instead of recurrence.",
            kind=ClaimKind.METHODOLOGICAL,
        ),
    ]
    card = ClaimCard(card_id="smoke", manuscript_ref=ref, claims=claims)

    # Pre-retrieve so the sync engine stays sync (mirrors the MCP tool).
    cache: dict[str, list] = {}
    for c in claims:
        cache[c.text] = await sub.retrieve(c.text, 8)

    def retrieve(query: str, _k: int) -> list:
        return cache.get(query, [])

    verify_claimcard(card, retrieve=retrieve, judge=judge, extractor=extractor, k=8)
    for c in card.claims:
        anchor = c.evidence[0].anchor_phrase[:90] + "…" if c.evidence else "—"
        print(f"\n[{c.verdict.value.upper():12}] {c.text}")
        print(f"    anchor: «{anchor}»")

    # ---------------- WRITE: draft a section from bullets ----------------
    _hr("WRITE  ·  draft_section (supported bullet / unsupported bullet)")
    outline = [
        "How many attention heads the model uses and the model dimension.",
        "The medical image segmentation dataset and the augmentation pipeline used.",
    ]
    raw_writer = make_writer()
    memo: dict[str, str] = {}

    def writer(bullet: str, passages: list[str]) -> str:
        if bullet not in memo:
            memo[bullet] = raw_writer(bullet, passages)
        return memo[bullet]

    # warm the bullet retrieval, then the written-sentence retrieval (verify re-retrieves)
    for b in outline:
        cache[b] = await sub.retrieve(b, 8)
    for b in outline:
        s = writer(b, [p.verbatim_text for p in cache.get(b, [])])
        if s not in cache:
            cache[s] = await sub.retrieve(s, 8)

    section = draft_section(
        outline, retrieve=retrieve, write=writer, judge=judge, extractor=extractor, k=8
    )
    print(render_draft_section(section, title="Smoke draft"))

    _hr("RESULT")
    honored = sum(1 for c in card.claims if c.verdict and c.verdict.value == "honored")
    print(f"REVIEW: {honored}/{len(card.claims)} honored · "
          f"WRITE: {len(section.anchored())}/{len(section.cards)} anchored, "
          f"{section.no_evidence_count()} flagged NO_EVIDENCE")
    print("Guarantee holds if: the false claim is NOT honored, and the unsupported bullet is "
          "flagged — never invented.")


if __name__ == "__main__":
    asyncio.run(main())
