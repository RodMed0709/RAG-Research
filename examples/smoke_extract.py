"""SMOKE: the FULL pipeline on real data, offline, no API key.

  PDF -> substrate (retrieve verbatim) -> extract (N-way + read-back) -> build SpecCard
      -> verify_consistency against a code snippet.

The extractor/reader here are TOY regex stand-ins for the production LLM (which is injected).
The point is that every seam connects on real passages, not that the toy extractor is smart.

Run:  python examples/smoke_extract.py
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path

from specrag import (
    Cat,
    LocatorKind,
    SpecCard,
    SpecField,
    State,
    ValueKind,
    ValueSpec,
    verify_consistency,
)
from specrag.extract import extract_field
from specrag.substrate import Substrate, make_jumper

PDF = Path(__file__).parent / "test_papers" / "label_dropout_2403.07818.pdf"
_NUM = re.compile(r"\b(\d+)\b")


def toy_extractor(passage_text: str, field_name: str) -> str | None:
    """Toy stand-in for the LLM extractor: first integer in the passage."""
    m = _NUM.search(passage_text)
    return m.group(1) if m else None


def toy_reader(verbatim: str, field_name: str) -> str | None:
    """Toy read-back (pretend different model): same first-integer read."""
    m = _NUM.search(verbatim)
    return m.group(1) if m else None


async def main() -> None:
    from paperqa import SentenceTransformerEmbeddingModel

    sub = Substrate(embedding_model=SentenceTransformerEmbeddingModel())
    print(f"ingesting {PDF.name} (offline, local embeddings)...")
    await sub.ingest(str(PDF), paper_ref="labeldropout2024echo", citation="arXiv:2403.07818")

    passages = await sub.retrieve("number of training epochs", k=3)
    p = passages[0]
    print(f"top passage: {p.page_range}  ({len(p.verbatim_text)} chars cached)\n")

    # EXTRACT (N-way agreement + read-back) — injected toy models
    out = extract_field(p, "epochs", extractor=toy_extractor, reader=toy_reader, n=2)
    print("ExtractOutcome:")
    print(f"  value={out.value!r}  agreement={out.agreement}  runs={out.n_runs}")
    print(f"  readback_ok={out.readback_ok}  verification_level={out.verification_level.value}\n")

    if out.value is None:
        print("toy extractor found no integer; pipeline still ran (flagged unverified).")
        return

    # BUILD a card field from the extracted value + a real jumper
    jumper = make_jumper(p, out.value)
    field = SpecField(
        name="epochs",
        category=Cat.HYPERPARAMETER,
        value_kind=ValueKind.NUMERIC,
        locator_kind=LocatorKind.LITERAL,
        value_spec=ValueSpec(kind=ValueKind.NUMERIC, equals=int(out.value)),
        moat_critical=True,
        verification_level=out.verification_level,
        jumper=jumper,
    )
    card = SpecCard(card_id="labeldropout2024echo::label-dropout", paper_ref="labeldropout2024echo",
                    method="label-dropout", fields=[field])
    print(f"built card {card.card_id} with 1 extracted field (verification_summary={card.verification_summary()})\n")

    # VERIFY generated code against the card — honored vs violated
    good = f"epochs = {out.value}\n"
    bad = f"epochs = {int(out.value) + 1}\n"
    for label, code in [("matching code", good), ("mismatched code", bad)]:
        v = verify_consistency(card, code,
                               locate=lambda f, c: (re.search(r"epochs\s*=\s*(\d+)", c) or [None, None])[1],
                               judge=lambda f, c: State.AMBIGUOUS)[0]
        flag = "BLOCK" if v.blocked else ("HUMAN" if v.needs_human else "ok")
        print(f"  {label:<16} -> {v.state.value:<10} [{flag}]  (moat-critical, card={out.verification_level.value})")


if __name__ == "__main__":
    asyncio.run(main())
