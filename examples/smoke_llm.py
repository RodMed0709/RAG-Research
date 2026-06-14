"""REAL-LLM smoke: DeepSeek as the actual judge/extractor (not a toy regex).

This is the first test of the THESIS itself: can the system, with a real LLM, tell apart an
augmentation applied in the correct phase (HONORED) from the wrong phase (VIOLATED), and
extract a value from a passage with an independent read-back? Needs DEEPSEEK_API_KEY (.env).

Run:  python examples/smoke_llm.py
"""
from __future__ import annotations

from specrag import (
    Cat,
    LocatorKind,
    Phase,
    SpecField,
    ValueKind,
    ValueSpec,
    VLevel,
    verify_field,
)
from specrag.extract import extract_field
from specrag.llm import load_env, make_extractor, make_judge, make_locator, make_reader
from specrag.speccard import Jumper
from specrag.substrate import Passage

load_env()


def jitter_field() -> SpecField:
    return SpecField(
        name="intensity_jitter", category=Cat.AUGMENTATION, value_kind=ValueKind.ENUM,
        locator_kind=LocatorKind.SEMANTIC,
        value_spec=ValueSpec(kind=ValueKind.ENUM, equals="intensity_jitter",
                             aliases=["intensity perturbation", "brightness jitter"]),
        phase=Phase.EVAL, moat_critical=True, verification_level=VLevel.HUMAN,
        jumper=Jumper(pq_dockey="d", verbatim_text="intensity jitter applied only at evaluation",
                      anchor_phrase="intensity jitter applied only at evaluation"),
    )


CODE_HONORED = (
    "for x, y in loader:\n"
    "    if phase == 'eval':\n"
    "        x = intensity_jitter(x, strength=0.1)  # eval-time robustness probe only\n"
    "    pred = model(x)\n"
)
CODE_VIOLATED = (
    "for x, y in train_loader:\n"
    "    x = intensity_jitter(x, strength=0.1)  # applied every TRAINING step\n"
    "    loss = criterion(model(x), y)\n"
)


def main() -> None:
    judge = make_judge()
    locate = make_locator()
    field = jitter_field()

    print("THESIS TEST — real DeepSeek judging augmentation phase (card says: jitter @ EVAL only)\n")
    for label, code in [("jitter @ eval  (expect HONORED, pass)", CODE_HONORED),
                        ("jitter @ train (expect VIOLATED, block/escalate)", CODE_VIOLATED)]:
        v = verify_field(field, code, locate=locate, judge=judge)
        outcome = "BLOCK" if v.blocked else ("HUMAN" if v.needs_human else "ok")
        print(f"  {label}")
        print(f"     -> state={v.state.value}  source={v.verdict_source}  [{outcome}]\n")

    print("EXTRACTION TEST — real DeepSeek extract + INDEPENDENT read-back\n")
    passage = Passage(
        pq_dockey="d", page_range="pages 5-6", doc_citation="cite",
        verbatim_text="The encoder was fine-tuned with a batch size of 8 per GPU for 200 epochs "
                      "using Adam with a learning rate of 1e-4.",
    )
    out = extract_field(passage, "batch size per GPU",
                        extractor=make_extractor(), reader=make_reader(),
                        extractor_id="deepseek-extractor", reader_id="deepseek-reader", n=2)
    print(f"  value={out.value!r}  agreement={out.agreement}  runs={out.n_runs}")
    print(f"  readback={out.readback_value!r}  readback_ok={out.readback_ok}  "
          f"independent={out.independent_readback}")
    print(f"  verification_level={out.verification_level.value}")


if __name__ == "__main__":
    main()
