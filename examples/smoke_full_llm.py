"""FLAGSHIP smoke: the ENTIRE autonomous loop with real DeepSeek at every seam, on a real PDF.

  paper PDF
    -> substrate.retrieve (offline local embeddings)
    -> DeepSeek extract + independent read-back  -> typed value
    -> build_field (typed ValueSpec) + make_jumper -> SpecCard
    -> DeepSeek generate code honoring the card
    -> verify the generated code (DeepSeek locates, code compares hard fields)
    -> stamp + check_stamp across a re-extraction

No toys anywhere except the choice of which value to chase. Needs DEEPSEEK_API_KEY (.env).

Run:  python examples/smoke_full_llm.py
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from specrag import (
    Cat,
    LocatorKind,
    SpecCard,
    ValueKind,
    build_field,
    check_stamp,
    generate_and_verify,
)
from specrag.extract import extract_field
from specrag.llm import load_env, make_extractor, make_generator, make_judge, make_locator, make_reader
from specrag.substrate import Substrate, make_jumper

PDF = Path(__file__).parent / "test_papers" / "label_dropout_2403.07818.pdf"


async def main() -> None:
    from paperqa import SentenceTransformerEmbeddingModel

    load_env()
    sub = Substrate(embedding_model=SentenceTransformerEmbeddingModel())
    print(f"[1] ingesting {PDF.name} (offline)...")
    await sub.ingest(str(PDF), paper_ref="labeldropout2024echo", citation="arXiv:2403.07818")

    print("[2] retrieving training-detail passages...")
    passages = await sub.retrieve("number of training epochs schedule training details", k=5)

    print("[3] DeepSeek extract 'number of training epochs' across passages (extract + read-back)...")
    extractor, reader = make_extractor(), make_reader()
    found = None
    for p in passages:
        out = extract_field(p, "number of training epochs", extractor=extractor, reader=reader,
                            extractor_id="deepseek-extractor", reader_id="deepseek-reader", n=2)
        print(f"    {p.page_range}: value={out.value!r} agreement={out.agreement} "
              f"readback_ok={out.readback_ok} -> {out.verification_level.value}")
        if out.value is not None and out.value.isdigit():
            found = (p, out)
            break
    if found is None:
        print("    (no clean epoch count agreed across passages; pipeline ran honestly, flagged. Stop.)")
        return
    passage, out = found

    print("[4] build typed card field + jumper...")
    try:
        field = build_field(
            "epochs", out.value, value_kind=ValueKind.NUMERIC,
            locator_kind=LocatorKind.LITERAL, category=Cat.HYPERPARAMETER,
            jumper=make_jumper(passage, out.value), verification_level=out.verification_level,
            moat_critical=True,
        )
    except ValueError as e:
        print(f"    build refused the value (loud, as designed): {e}")
        return
    card = SpecCard(card_id="labeldropout2024echo::label-dropout", paper_ref="labeldropout2024echo",
                    method="label-dropout", fields=[field])
    print(f"    card field: epochs == {field.value_spec.equals} (level {out.verification_level.value})")

    print("[5] DeepSeek GENERATE code honoring the card, then VERIFY it...")
    result = generate_and_verify(card, generator=make_generator(),
                                 locate=make_locator(), judge=make_judge())
    print("    --- generated code (first 6 lines) ---")
    for ln in result.code.splitlines()[:6]:
        print(f"      {ln}")
    v = result.verdicts[0]
    print(f"    verify: {v.field_name} -> {v.state.value} via {v.verdict_source}  "
          f"blocked={result.blocked} needs_human={result.needs_human}")

    print("[6] stamp + re-extraction drift check...")
    changed = str(int(out.value) * 2)
    card_v2 = SpecCard(
        card_id="labeldropout2024echo::label-dropout", paper_ref="labeldropout2024echo",
        method="label-dropout", version=2,
        fields=[build_field("epochs", changed, value_kind=ValueKind.NUMERIC,
                            locator_kind=LocatorKind.LITERAL, category=Cat.HYPERPARAMETER,
                            jumper=make_jumper(passage, out.value), moat_critical=True)],
    )
    report = check_stamp(result.stamp, card_v2)
    print(f"    re-extracted epochs {out.value} -> {changed} (v2): stale={report.stale}  ({report.reason})")
    print("\nFull autonomous loop ran with real DeepSeek at every LLM seam.")


if __name__ == "__main__":
    asyncio.run(main())
