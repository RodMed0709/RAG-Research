"""SMOKE: ingest a REAL echocardiography PDF via PaperQA2, retrieve verbatim passages
with local embeddings (no API key), and build a self-sufficient Jumper.

This exercises the whole substrate path end-to-end on real data — the "make it run".

Run:  python examples/smoke_substrate.py
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from rag_research.substrate import Substrate, make_jumper

PDF = Path(__file__).parent / "test_papers" / "label_dropout_2403.07818.pdf"
QUERIES = ["batch size used for training", "learning rate and optimizer", "dropout regularization"]


async def main() -> None:
    from paperqa import SentenceTransformerEmbeddingModel

    print("loading local embedding model (no API key)...")
    emb = SentenceTransformerEmbeddingModel()
    sub = Substrate(embedding_model=emb)

    print(f"ingesting {PDF.name} ...")
    ref = await sub.ingest(str(PDF), paper_ref="labeldropout2024echo", citation="Label Dropout, arXiv:2403.07818")
    print(f"  paper_ref = {ref}  (stable rag_research id, NOT the PaperQA2 dockey)\n")

    for q in QUERIES:
        print(f"== query: {q!r} ==")
        passages = await sub.retrieve(q, k=3)
        for i, p in enumerate(passages, 1):
            snippet = " ".join(p.verbatim_text.split())[:160]
            print(f"  [{i}] {p.page_range or 'page ?':<10} dockey={p.pq_dockey[:12]}…")
            print(f"      \"{snippet}…\"")
        print()

    # build a real jumper: find a number in the top batch-size passage
    passages = await sub.retrieve("batch size used for training", k=3)
    for p in passages:
        for token in p.verbatim_text.split():
            digits = "".join(c for c in token if c.isdigit())
            if digits and "batch" in p.verbatim_text.lower():
                j = make_jumper(p, digits)
                if j is not None:
                    print("built Jumper from real passage:")
                    print(f"  pq_dockey   = {j.pq_dockey[:16]}…")
                    print(f"  page_range  = {j.page_range}")
                    print(f"  anchor      = \"{j.anchor_phrase[:90]}…\"")
                    print(f"  char_span   = {j.char_span}  (None = homonym, flag for human)")
                    print(f"  verbatim cached = {len(j.verbatim_text)} chars")
                    return
    print("(no numeric batch token surfaced in top passages — retrieval still ran)")


if __name__ == "__main__":
    asyncio.run(main())
